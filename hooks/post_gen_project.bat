if not exist .git (
    echo "Creating git repo."
    git init
)

echo "adding initial commit so gitversioning works."
git add --all
git commit -am "Initial commit from Cookiecutter template"


echo "Creating virtual environment for development in new directory."
py -{{cookiecutter.python_version}} -m venv venv
call .\venv\Scripts\activate.bat
python -m pip install pip-tools

echo "Updating dependencies"
pip-compile --output-file=requirements.txt pyproject.toml
pip-compile --extra=dev --output-file=dev-requirements.txt -c requirements.txt  pyproject.toml

echo "Installing dependencies"
pip-sync .\dev-requirements.txt .\requirements.txt
