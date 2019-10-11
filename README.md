![Current Build Status](https://travis-ci.org/flyingcircusio/batou.svg?branch=master)

batou helps you to automate your application deployments:

* You create a model of your deployment using a simple but powerful Python API.
* You configure how the model applies to hosts in different environments.
* You verify and run the deployment with the batou utility.

Getting started with a new project is easy::

    $ mkdir myproject
    $ cd myproject
    $ curl https://bitbucket.org/flyingcircus/batou/raw/tip/src/batou/bootstrap-template -o batou
    $ chmod +x batou
    $ ./batou

Here's a minimal application model::

    $ mkdir -p components/myapp
    $ cat > components/myapp/component.py
    from batou.component import Component
    from batou.lib.python import VirtualEnv, Package
    from batou.lib.supervisor import Program

    class MyApp(Component):

        def configure(self):
            venv = VirtualEnv('2.7')
            self += venv
            venv += Package('myapp')
            self += Program('myapp',
                command='bin/myapp')

And here's a minimal environment::

    $ mkdir environments
    $ cat > environments/dev.cfg
    [environment]
    connect_method = local

    [hosts]
    localhost = myapp

To deploy this, you run::

    $ ./batou deploy dev

Check the `detailed documentation <http://batou.readthedocs.org>`_ to get going with a more ambitious project.


## Features

* Separate your application model from environments
* Supports idempotent operation for incremental deployments
* Deploy to multiple hosts simultaneously
* Automated dependency resolution for multi-host
  scenarios
* No runtime requirements on your application
* Encrypted secrets with multiple access levels: store your
  SSL certificates, SSH keys, service secrets and more to get true 1-button deployments.
* Deploy to local machines, Vagrant, or any SSH host
* Broad SSH feature support by using OpenSSH through execnet
* Only few dependencies required on the remote host
* Ships with a library of components for regularly needed
  tasks
* self-bootstrapping and self-updating - no additional
  scripting needed

## License

The project is licensed under the 2-clause BSD license.