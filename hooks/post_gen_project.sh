#!/bin/bash
if [ ! -d ".git" ]; then
    echo "Creating git repository."
    git init
fi

echo "adding initial commit so gitversioning works."
git add --all
git commit -am "Initial commit from Cookiecutter template"

echo "Creating virtual environment for development in new directory."
ci/linux/create_venv.sh
echo "Updating dependencies"
ci/linux/update_dependencies.sh
echo "Installing dependencies"
ci/linux/install_dependencies.sh
