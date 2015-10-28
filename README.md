The python documentation is done via sphinx and is hosted via github pages.

You can find it [here](http://www.project8.org/dripline) or [here](http://project8.github.io/dripline) (they are literally the same).

# Quick Install

For the sake of an example, I'll assume the following:

1. You've activated the virtualenvironment you want to use
2. You are currently in a directory where it is acceptable to place source

```bash
echo "clone dripline and switch to the most recent tag"
git clone git@github.com:project8/dripline
cd dripline
git checkout master
echo "install dripline with some convenience options on"
echo "zsh users will need to change this line to escape the square brackets"
pip install . dripline[other]
cd ..

echo "clone dragonfly and switch to the most recent tag"
git clone git@github.com:project8/dragonfly
cd dragonfly
git checkout master
echo "install dragonfly without any optional extras"
pip install . dragonfly
cd ..
```
