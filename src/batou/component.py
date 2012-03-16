# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

from batou.template import TemplateEngine
import batou
import batou.utils
import contextlib
import filecmp
import logging
import os
import os.path
import re
import shutil
import subprocess

logger = logging.getLogger(__name__)


def load_components_from_file(filename):
    g = l = {}
    g.update(globals())
    oldcwd = os.getcwd()
    defdir = os.path.dirname(filename)
    os.chdir(defdir)
    execfile(filename, g, l)
    for candidate in l.values():
        if candidate in globals().values():
            # Ignore anything we pushed into the globals before execution
            continue
        if (isinstance(candidate, type) and
            issubclass(candidate, Component)):
            factory = RootComponentFactory(
                    candidate.__name__.lower(),
                    candidate,
                    defdir)
            yield factory
    os.chdir(oldcwd)


class Component(object):

    namevar = ''

    def __init__(self, namevar=None, **kw):
        if self.namevar:
            if namevar is None:
                raise ValueError('Namevar %s required' % self.namevar)
            kw[self.namevar] = namevar
        self.__dict__.update(kw)
        self.hooks = {}
        self.sub_components = []

    # Configuration phase

    def prepare(self, service, environment, host, root, parent=None):
        self.service = service
        self.environment = environment
        self.host = host
        self.root = root
        self.parent = parent
        self.configure()
        self += self.get_platform()

    def configure(self):
        """Configure the component.

        At this point the component has been embedded into the overall
        structure, so that service, environment, host, root, and parent are
        set.

        Also, any environment-specific attributes have been set.

        At this point the component should add sub-components as required and
        use the configured values so that calls to verify/update can, without
        much overhead, perform their work.

        Also, any computation that happens in the configure phase is run while
        building the model so that this can be used to ensure some level of
        internal consistency before invoking the remote control layer.
        """
        pass

    # Deployment phase

    def deploy(self):
        for sub_component in self.sub_components:
            sub_component.deploy()
        try:
            self.verify()
        except batou.UpdateNeeded:
            logger.debug('Updating {}'.format(self._breadcrumbs))
            self.update()

    def verify(self):
        """Verify whether this component has been deployed correctly or needs
        to be updated.

        Raises the UpdateNeeded exception if an update is needed.

        Implemented by specific components.
        """
        pass

    def update(self):
        """Is called if the verify method indicated that an update is needed.

        This method needs to handle all cases to move the current deployed
        state of the component, whatever it is, to the desired new state.

        Implemented by specific components.

        """
        pass

    # Sub-component mechanics

    def __add__(self, component):
        """Add a new sub-component.

        This will also automatically prepare the added component.

        """
        # Allow `None` components to flow right through. This makes the API a
        # bit more convenient in some cases, e.g. with platform handling.
        if component is not None:
            self.sub_components.append(component)
            component.prepare(self.service, self.environment,
                              self.host, self.root, self)
        return self

    # Platform mechanics

    @classmethod
    def add_platform(cls, name, platform):
        if not '_platforms' in cls.__dict__:
            cls._platforms = {}
        cls._platforms[name] = platform

    def get_platform(self):
        """Return the platform component for this component if one exists."""
        platforms = getattr(self, '_platforms', {})
        return platforms.get(self.environment.platform, lambda:None)()

    # Component (convenience) API 

    def assert_file_is_current(self, result, requirements=[]):
        if not os.path.exists(result):
            raise batou.UpdateNeeded()
        current = os.stat(result).st_mtime
        for requirement in requirements:
            if current < os.stat(requirement).st_mtime:
                raise batou.UpdateNeeded()

    def cmd(self, cmd):
        return subprocess.check_output([cmd], shell=True)

    def touch(self, filename):
        open(filename, 'wa').close()

    def expand(self, string):
        engine = batou.template.MakoEngine()
        return engine.expand(string, self._template_args())

    def template(self, filename, component=None):
        engine = batou.template.MakoEngine()
        return engine.template(
            filename, self._template_args(component=component))

    def _template_args(self, component=None):
        if component is None:
            component = self
        args = dict(
            host=self.host,
            environment=self.environment,
            service=self.environment.service,
            component=self if component is None else component)
        return args

    @property
    def secrets(self):
        return self.find_hooks('secrets')[0]

    @contextlib.contextmanager
    def chdir(self, path):
        old = os.getcwd()
        os.chdir(path)
        yield
        os.chdir(old)

    def find_hooks(self, expression, host=None):
        hooks = []
        components = []
        for candidate_host in self.environment.hosts.values():
            if host is not None and candidate_host != host:
                continue
            for root in candidate_host.components:
                components.append(root.component)
        while components:
            current = components.pop()
            components.extend(current.sub_components)
            if expression in current.hooks:
                hooks.append(current.hooks[expression])
        return hooks

    # internal methods

    @property
    def _breadcrumbs(self):
        result = ''
        if self.parent is not None:
            result += self.parent._breadcrumbs + ' > '
        result += self._breadcrumb
        return result

    @property
    def _breadcrumb(self):
        result = self.__class__.__name__
        name = getattr(self, self.namevar, None)
        if name:
            result += '({})'.format(name)
        return result


class RootComponentFactory(object):

    def __init__(self, name, factory, defdir):
        self.name = name
        self.factory = factory
        self.defdir = defdir

    def __call__(self, service, environment, host, config):
        component = self.factory(**config)
        root = RootComponent(self.name, component, self.defdir)
        component.prepare(service, environment, host, root)
        return root


class RootComponent(object):
    """Wrapper to manage top-level components assigned to hosts in an
    environment.

    Root components have a name and "own" the working directory for itself and
    its sub-components.

    """

    def __init__(self, name, component, defdir):
        self.component = component
        self.name = name
        self.defdir = defdir

    @property
    def compdir(self):
        return '%s/work/%s' % (self.component.service.base, self.name)

    def _update_compdir(self):
        if not os.path.exists(self.compdir):
            os.makedirs(self.compdir)

    def deploy(self):
        self._update_compdir()
        os.chdir(self.compdir)
        self.component.deploy()