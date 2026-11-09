# PythonTemplate

This is an example of a python package / collection of scripts for Wanda team.
Use this as a template for starting your project. 

# Copying this template

The template is build using cookiecutter. This is a commandline utility which can initialize a template using
a list of input variables. To copy this template:

```bash
pip install cookiecutter
cookiecutter https://github.com/Deltares-research/template-python-wanda
```

Running this command it will ask a number of questions such as the name and e-mail of the main maintainer as well
as the project name. After completing the survey, the repo is initialized locally and ready to be committed to Github.

First, create the Github repository. Then run the following locally:

```bash
cd <whatever your repo is called>
git init
git remote add origin <your repo name>.git  # Github will show this URL in your repo.
git add .
git commit -m "Initial commit."
git push origin main
```

Your repository should now be ready.
