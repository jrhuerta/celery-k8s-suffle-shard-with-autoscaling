#!/usr/bin/env python3
import logging
import signal
import sys
import threading
import time

import click
import prometheus_client
import redis
from celery import Celery

LOG_FORMAT = "[%(asctime)s] %(name)s:%(levelname)s: %(message)s"

_monitored_queues = set()

QUEUE_LENGTH = prometheus_client.Gauge(
    "celery_queue_length", "Number of tasks sent", ["namespace", "queue"]
)
WORKERS = prometheus_client.Gauge(
    "celery_workers_total", "Number of active workers", ["namespace", "queue"]
)


class BrokerMonitorThread(threading.Thread):
    def __init__(self, broker_url, *args, **kwargs):
        self._app = Celery(broker=broker_url)

        self._logger = logging.getLogger("broker-monitor")
        super(BrokerMonitorThread, self).__init__(*args, **kwargs)

    def _append_queue(self, event):
        try:
            self._log_event(event)
            queue_name = event.get("queue")
            if queue_name not in _monitored_queues:
                self._logger.info("%s: added to monitored queues." % queue_name)
            _monitored_queues.add(queue_name)
        except Exception:
            self._logger.exception("Unable to add queue from event. %r", event)

    def _log_event(self, event):
        self._logger.debug(event)

    def run(self):
        while True:
            try:
                with self._app.connection() as connection:
                    recv = self._app.events.Receiver(
                        connection,
                        handlers={
                            "task-sent": self._append_queue,
                            "worker-online": self._log_event,
                            "worker-heartbeat": self._log_event,
                            "worker-offline": self._log_event,
                        },
                    )
                    recv.capture(limit=None, timeout=None, wakeup=True)
            except Exception as ex:
                self._logger.exception("Queue monitor error")
                time.sleep(5)


class MetricUpdateThread(threading.Thread):
    def __init__(self, redis_url, namespace, refresh_interval, *args, **kwargs):
        self._redis_url = redis_url
        self._namespace = namespace
        self._refresh_interval = refresh_interval
        self._logger = logging.getLogger("metric-update")
        super(MetricUpdateThread, self).__init__(*args, **kwargs)

    def run(self):
        client = redis.from_url(self._redis_url)
        while True:
            for q in _monitored_queues:
                try:
                    QUEUE_LENGTH.labels(self._namespace, q).set(client.llen(q))
                except Exception as ex:
                    self._logger.exception("{}: error updating metrics".format(q))
            time.sleep(self._refresh_interval)


def shutdown(signum, frame):  # pragma: no cover
    """
    Shutdown is called if the process receives a TERM/INT signal.
    """
    logging.info("Shutting down")
    sys.exit(0)


@click.command(context_settings={"auto_envvar_prefix": "CELERY_MONITOR"})
@click.option(
    "--broker-url",
    "-b",
    type=click.STRING,
    show_default=True,
    show_envvar=True,
    default="redis://redis:6379/0",
    help="URL to the Celery broker.",
)
@click.option(
    "--listen-address",
    "-l",
    type=click.STRING,
    show_default=True,
    show_envvar=True,
    default="0.0.0.0:9540",
    help="Address the HTTPD should listen on.",
)
@click.option(
    "--namespace",
    "-n",
    type=click.STRING,
    show_default=True,
    show_envvar=True,
    default="celery",
    help="Namespace for metrics.",
)
@click.option(
    "--refresh",
    "-r",
    type=click.INT,
    show_default=True,
    show_envvar=True,
    default=5,
    help="Refresh interval in seconds.",
)
@click.option(
    "--dynamic",
    "-d",
    is_flag=True,
    show_envvar=True,
    help="Detect new queues dynamically.",
)
@click.option(
    "--queues",
    "-q",
    type=click.STRING,
    show_envvar=True,
    help="Comma separated list of queues to monitor.",
)
@click.option(
    "--verbose", "-v", is_flag=True, show_envvar=True, help="Enable verbose logging."
)
def main(broker_url, listen_address, namespace, dynamic, queues, refresh, verbose):
    if verbose:
        logging.basicConfig(level=logging.DEBUG, format=LOG_FORMAT)
    else:
        logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

    _monitored_queues.update([c.strip() for c in queues.split(",")])
    if _monitored_queues:
        logging.info("Queues: %r" % _monitored_queues)

    if dynamic:
        logging.info("Dynamic queue detection enabled.")
        qm = BrokerMonitorThread(broker_url=broker_url)
        qm.daemon = True
        qm.start()

    mu = MetricUpdateThread(
        redis_url=broker_url, namespace=namespace, refresh_interval=refresh
    )
    mu.daemon = True
    mu.start()

    address, port = listen_address.split(":")
    prometheus_client.start_http_server(int(port), address)
    logging.info("Listening on {}".format(listen_address))

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    while True:
        signal.pause()


if __name__ == "__main__":
    main()
