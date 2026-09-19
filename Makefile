up:
	docker compose up --build

down:
	docker compose down -v

python-test:
	cd python-ai && pytest -q

java-test:
	cd java-tools && mvn test

eval:
	cd evals && python evaluate.py
