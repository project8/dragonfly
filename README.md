# Dragonfly

**TODO: this README needs to be replaced with something specific to Dragonfly**

This repo is an example of extending the dripline namespace with an extension python package.

It serves several purposes:
1. It leverages (will leverage) travis-ci to test that code changes don't break our ability to add extension modules.
2. It is (will be) the example used in the documentation for writing extensions
3. It includes working examples of the various boilerplate required.

## Quick start
- Run the dripline-python container, with the repo mounted in a known path.
- Build this plugin with `pip install <path/to/the/mount/point>`
- Run the example config with `dl-serve -c /path/to/the/mount/point/kv_store_tutorial.yaml` (you probably also need `--auth-file /some/path/to/auths.json`) in a known path.

## Writing your own extension
Starting with dripline-python v4.0.0, dripline-python supports using namespace packages to add classes to the dripline namespace for use in applications.
This model will allow individual projects to more naturally add their own customized components, including installing any extra dependencies and allowing implementations to span multiple source files in a reasonable way, while still using the common command line tools including `dl-serve`.
In order to add your own components, you can start with this repo as an example or a template, the steps are:

1. Create a new python package. You can copy the setup.py file and the dripline directory structure from this repo into your own repo for this purpose.
2. Note that the directory structure requires that the `dripline` directory be empty except for its subdirectory `extensions` and that `extensions` have exactly the `__init__.py` file as is here.
3. The `dripline/extensions/jitter` directory is an example, your plugin should have a different name of your choice.
4. Within your plugin's folder, the `__init__.py` file must:
   1. import the classes you've imlemented and define an `__all__` list of the objects you want to add to the namespace
   2. define a `version` data member which is a scarab.VersionSemantic() instance, here we extract the version from the python package but you can populate that object in whatever method works best for you.
5. Optionally, copy the Dockerfile, make sure that the copy and working directory location used are unique to your plugin and confirm that the base image tag is current (or at least that you're happy with that version).
6. Implement your custom classes and run your service in the usual way, `dl-serve` will be able to find them as it creates the class instances in the usual way.

## Extra notes
If you're using docker-compose, you can use the path to this directory (or your plugin's equivalent directory), as the value of a `build:` key when defining a service.
That will result in a container with your plugin built on top of the base dripline-python.
You can also add a volume mount which matches the Dockerfile's copy so that your local source tree is available in the container, making it easy to iterate when doing code development.
