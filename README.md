# livescores-8x

# Streamlit app

Introduce streamlit app

## Install Python, Poetry
  
1. Install Python 3.10.11 or above
```
pyenv install 3.10.11
echo "3.10.11" >> .python-version
```
 
2. Install Poetry
```
pip install poetry
```

3. Configure project
`copy .env-template .env`
then install dependencies
`poetry install`


4. Run Streamlit app (stapp.py)
```
poetry shell
python -m streamlit run streamlit_app.py
```