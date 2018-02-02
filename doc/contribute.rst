Contribute
##########

Dragonfly has been exclusively developed by the `Project 8 collaboration <http://www.project8.org>`_, but was intentionally designed with flexibility of application.
As always, `dragonfly is on github <github.com/project8/dragonfly>`_.

Branching
=========

Branches are cheap, lets do more of those.
For more details, `this branching model <nvie.com/posts/a-successful-git-branching-model>`_ has served us very well to date.
In particular, please note that master is for tagged/release versions while develop is the latest working version.
We name branches off of develop as ``feature/<description>`` and bug fixes off of master as ``hotfix/<description>`` so that they are sorted and easier to navigate.
You're welcome and encouraged to push your feature branch to github, we're not going to judge you for things that are incomplete and appreciate not losing work if you move on or lose your laptop (at a minimum, we suggest pushing at the end of your work day).

Merging
=======

Merging follows the instruction from the branching section above in most cases, but there are a few additional notes:

  - If you'd like for someone to look over your changes before they are integrated, please push your branch and create a pull request
  - If you are new to dripline-python, we ask that you use a PR for anything other than a very minor change when contributing to develop
  - In the near term, we're planning to require PRs for all merges into the master branches when new releases are created

Mocking
=======

TODO_DOC: copied from old, but possibly useful (all the TDD stuff just wiped)

Dripline is inherently network oriented, but when we are running tests we want to be isolated from connections to the
network.  To get around this and test the functionality of our code, it is necessary to *mock* certain functions and
classes so that the behavior of our code can be tested independently of communication with the outside world.

This may be a limitation in some respect, but note that you can mock a function in such a way that it will return whatever
you might expect from a remote host, and therefore preserve the logic of your program.

Mocking is a subject unto itself - see examples in ``test_node.py``, or read more extensively about the mocking capabilities
in py.test `here <http://pytest.org/latest/monkeypatch.html>`_
