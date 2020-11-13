FROM python:3

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000
#CMD FLASK_APP=main.py flask run -h 0.0.0.0 -p 5000
CMD ["/usr/local/bin/newrelic-admin", "run-program", "uwsgi", "--ini", "/app/uwsgi.ini"]
