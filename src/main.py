import logging
import time
import random

from flask import Flask, jsonify
from celery import Celery

logging.basicConfig(level=logging.DEBUG)


fapp = Flask(__name__)
capp = Celery('tasks', broker='redis://redis:6379/0')
capp.conf.task_send_sent_event = True


@capp.task
def sleep(t):
	if random.randint(0,100) % 10 == 1:
		raise RuntimeError()
	time.sleep(t)



@fapp.route('/status', methods=['GET'])
def app_status():
    return jsonify({"status": "OK"})


@fapp.route('/task/create/<string:queue>', methods=['POST'])
def task_create(queue):
    sleep.apply_async((random.randint(0,5),), queue=queue)
    return jsonify({"message": "Task created."})
