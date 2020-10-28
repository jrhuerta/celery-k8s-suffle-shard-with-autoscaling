all: app worker monitor

app: src/Dockerfile.app src/requirements.txt src/main.py
	docker build -t jrhuerta/celery-demo:app -f src/Dockerfile.app src/
	docker push jrhuerta/celery-demo:app

worker: src/Dockerfile.worker src/requirements.txt src/main.py
	docker build -t jrhuerta/celery-demo:worker -f src/Dockerfile.worker src/
	docker push jrhuerta/celery-demo:worker

monitor: src/Dockerfile.monitor src/requirements.txt src/monitor.py
	docker build -t jrhuerta/celery-demo:monitor -f src/Dockerfile.monitor src/
	docker push jrhuerta/celery-demo:monitor

