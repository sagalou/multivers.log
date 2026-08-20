.PHONY: help eval test back front install

help:
	@echo "make install  installe les dependances back et front"
	@echo "make back     lance l'API sur le port 8000"
	@echo "make front    lance l'interface sur le port 5173"
	@echo "make eval     rejoue les cas d'evaluation et affiche le score"
	@echo "make test     lance les tests automatises"

install:
	python3 -m venv venv
	venv/bin/pip install -r requirements.txt
	cd front && npm install

back:
	venv/bin/uvicorn app.main:app --reload --port 8000

front:
	cd front && npm run dev

eval:
	venv/bin/python eval/run_eval.py

test:
	venv/bin/python -m pytest tests/ -v
