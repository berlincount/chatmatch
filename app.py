# -*- coding: utf-8 -*-
from flask import Flask, render_template, send_from_directory
from collections import OrderedDict
import flask_bootstrap
import json
import os

app = Flask(__name__)
app.config['BOOTSTRAP_BOOTSWATCH_THEME'] = "cyborg"
app.config['CHATAPP_NAME'] = 'TestName'
app.config['CHATAPP_SHORT_NAME'] = 'TestShortName'
app.config['CHATAPP_TITLE'] = "TestTitle"
app.config['CHATAPP_DESCRIPTION'] = "TestDescription"
app.config['CHATAPP_THEME_COLOR'] = '#ff5555'
app.config['CHATAPP_BACKGROUND_COLOR'] = '#5555ff'
app.config['CHATAPP_CSS'] = """
    pre {
      background: #ddd;
      padding: 10px;
    }
    h2 {
      margin-top: 20px;
    }
    footer {
      margin: 20px;
    }
"""

def get_config(key):
  return app.config[key]

def list_themes():
  base = os.path.join(os.path.dirname(flask_bootstrap.__file__), 'static', 'bootstrap5', 'css', 'bootswatch')

  themes = OrderedDict()
  themes['default'] = 'none'

  for directory in sorted(os.listdir(base)):
    with open(f'{base}/{directory}/_bootswatch.scss') as scss:
      for line in scss:
        name = line.strip()[3:]
        break
    themes[directory] = name

  return json.dumps(themes)

app.jinja_env.globals.update(get_config=get_config, list_themes=list_themes)

bootstrap = flask_bootstrap.Bootstrap5(app)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/talks')
def talks():
    return render_template('talks.html')

@app.route('/calendar')
def calendar():
    return render_template('calendar.html')

@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/site.webmanifest')
def site_webmanifest():
    return render_template('site.webmanifest')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory('static', 'favicon.ico')

if __name__ == '__main__':
    app.run(debug=True)
