#!/usr/bin/env python3

import itertools
import json
import logging
import os
import random
import time

from celery import Celery
from flask import abort, Flask, jsonify, request
from redis import Redis

logging.basicConfig(level=logging.DEBUG)

fapp = Flask(__name__)
capp = Celery(
    "tasks", broker=os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0")
)
capp.conf.task_send_sent_event = True


class ShardManager:
    def __init__(
        self, shard_name: str, total_queues: int, queues_per_set: int, redis: Redis
    ):
        self._shard_name = f"shardmanager:{shard_name}"
        self._unasigned_shards_key = f"{self._shard_name}:unasigned_shards"
        self._redis = redis
        self.generate_shards(total_queues, queues_per_set)

    def _clear_shard_assignments(self):
        keys = self._redis.get(f"{self._shard_name}*")
        self._redis.delete(*keys)

    def generate_shards(self, total_queues: int, queues_per_set: int):
        self._clear_shard_assignments()
        shards = [
            json.dumps(t)
            for t in itertools.combinations(range(total_queues), queues_per_set)
        ]
        random.shuffle(shards)
        self._redis.lpush(
            self._unasigned_shards_key,
            shards,
        )

    def get_queue(self, tenant: str) -> str:
        ts_name = f"{self._shard_name}:{tenant}"
        queue = self._redis.rpoplpush(ts_name, ts_name)
        if queue is None:
            nshard = json.loads(self._redis.rpop(self._unasigned_shards_key))
            self._redis.lpush(ts_name, *nshard)
            queue = self._redis.rpoplpush(ts_name, ts_name)
        return queue.decode("utf-8")


shard_manager = ShardManager(
    shard_name=os.environ.get("CELERY_SHARD_NAME", "celery"),
    total_queues=int(os.environ.get("CELERY_QUEUES_TOTAL", 10)),
    queues_per_set=int(os.environ.get("CELERY_QUEUES_PER_SET", 5)),
    redis=Redis.from_url(os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0")),
)


@capp.task
def sleep(t):
    if random.randint(0, 100) % 10 == 1:
        raise RuntimeError()
    time.sleep(t)


@fapp.route("/status", methods=["GET"])
def app_status():
    return jsonify({"status": "OK"})


@fapp.route("/task/create/<string:tenant>", methods=["POST"])
def task_create(tenant):
    queue = shard_manager.get_queue(tenant)
    sleep.apply_async((random.randint(5, 10),), queue="queue{}".format(queue))
    return jsonify(
        {"host": os.environ.get("HOSTNAME"), "queue": queue, "message": "Task created."}
    )


@fapp.route("/shards/regenerate", methods=["POST"])
def shards_setup():
    try:
        data = request.json()
        shard_manager.generate_shards(data["total_queues"], data["queues_per_set"])
        return jsonify(
            {
                "total_queues": data["total_queues"],
                "queues_per_set": data["queues_per_set"],
                "message": "Success",
            }
        )
    except KeyError:
        abort(400)
