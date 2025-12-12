#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from enum import Enum
from flask import Flask, render_template, send_from_directory
from collections import OrderedDict
import flask_bootstrap
from flask_wtf import FlaskForm, CSRFProtect
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Integer, String
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped, mapped_column
import json
import os

app = Flask(__name__)
#app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///dev.sqlite3'
app.config['BOOTSTRAP_BOOTSWATCH_THEME'] = "cyborg"
app.config['CHATAPP_NAME'] = 'ChatMatch'
app.config['CHATAPP_SHORT_NAME'] = 'ChatMatch'
app.config['CHATAPP_TITLE'] = "ChatMatch"
app.config['CHATAPP_DESCRIPTION'] = "App to match discussion partitions to topics and timeslots"
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

class ChatMatch(DeclarativeBase):
    pass

bootstrap = flask_bootstrap.Bootstrap5(app)
db = SQLAlchemy(app, model_class=ChatMatch)
csrf = CSRFProtect(app)


class Topic(db.Model):
    __tablename__ = 'topic_table'

    id: Mapped[int] = mapped_column(primary_key=True)
    topic: Mapped[str] = mapped_column(unique=True)
    min_users: Mapped[int]
    max_users: Mapped[int]
    creator: Mapped[int] = mapped_column(ForeignKey("user_table.id"))
    create_time: Mapped[int]
    editor: Mapped[int] = mapped_column(ForeignKey("user_table.id"))
    edit_time: Mapped[int]

    __table_args__ = (UniqueConstraint("topic"),)

class User(db.Model):
    __tablename__ = 'user_table'

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str]
    nick: Mapped[str]
    magic: Mapped[str]
    create_time: Mapped[int]
    edit_time: Mapped[int]
    lastuse_time: Mapped[int]

    __table_args__ = (UniqueConstraint("email"),UniqueConstraint("nick"),)

class Slot(db.Model):
    __tablename__ = 'slot_table'

    id: Mapped[int] = mapped_column(primary_key=True)
    topic: Mapped[int] = mapped_column(ForeignKey("topic_table.id"))
    start_time: Mapped[int]
    duration: Mapped[int]
    creator: Mapped[int] = mapped_column(ForeignKey("user_table.id"))
    create_time: Mapped[int]
    editor: Mapped[int] = mapped_column(ForeignKey("user_table.id"))
    edit_time: Mapped[int]

class Match(db.Model):
    __tablename__ = 'match_table'

    id: Mapped[int] = mapped_column(primary_key=True)
    slot: Mapped[int] = mapped_column(ForeignKey("slot_table.id"))
    user: Mapped[int] = mapped_column(ForeignKey("user_table.id"))
    create_time: Mapped[int]
    confirmed: Mapped[bool]
    confirm_time: Mapped[int]
    cancel_time: Mapped[int]

with app.app_context():
    db.drop_all()
    db.create_all()
    # for i in range(20):
    #     url = 'mailto:x@t.me'
    #     if i % 7 == 0:
    #         url = 'www.t.me'
    #     elif i % 7 == 1:
    #         url = 'https://t.me'
    #     elif i % 7 == 2:
    #         url = 'http://t.me'
    #     elif i % 7 == 3:
    #         url = 'http://t'
    #     elif i % 7 == 4:
    #         url = 'http://'
    #     elif i % 7 == 5:
    #         url = 'x@t.me'
    #     m = Message(
    #         text=f'Message {i+1} {url}',
    #         author=f'Author {i+1}',
    #         create_time=4321*(i+1)
    #         )
    #     if i % 2:
    #         m.category = MyCategory.CAT2
    #     if i % 4:
    #         m.draft = True
    #     db.session.add(m)
    db.session.commit()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/form', methods=['GET', 'POST'])
def test_form():
    form = HelloForm()
    if form.validate_on_submit():
        flash('Form validated!')
        return redirect(url_for('index'))
    return render_template(
        'form.html',
        form=form,
        telephone_form=TelephoneForm(),
        contact_form=ContactForm(),
        im_form=IMForm(),
        button_form=ButtonForm(),
        example_form=ExampleForm(),
        inline_form=ExampleFormInline(),
        horizontal_form=ExampleFormHorizontal()
    )


@app.route('/nav', methods=['GET', 'POST'])
def test_nav():
    return render_template('nav.html')


@app.route('/bootswatch', methods=['GET', 'POST'])
def test_bootswatch():
    form = BootswatchForm()
    if form.validate_on_submit():
        if form.theme_name.data == 'default':
            app.config['BOOTSTRAP_BOOTSWATCH_THEME'] = None
        else:
            app.config['BOOTSTRAP_BOOTSWATCH_THEME'] = form.theme_name.data
        flash(f'Render style has been set to {form.theme_name.data}.')
    else:
        if app.config['BOOTSTRAP_BOOTSWATCH_THEME'] is not None:
            form.theme_name.data = app.config['BOOTSTRAP_BOOTSWATCH_THEME']
    return render_template('bootswatch.html', form=form)


@app.route('/pagination', methods=['GET', 'POST'])
def test_pagination():
    page = request.args.get('page', 1, type=int)
    pagination = Message.query.paginate(page=page, per_page=10)
    messages = pagination.items
    return render_template('pagination.html', pagination=pagination, messages=messages)


@app.route('/flash', methods=['GET', 'POST'])
def test_flash():
    flash('A simple default alert—check it out!')
    flash('A simple primary alert—check it out!', 'primary')
    flash('A simple secondary alert—check it out!', 'secondary')
    flash('A simple success alert—check it out!', 'success')
    flash('A simple danger alert—check it out!', 'danger')
    flash('A simple warning alert—check it out!', 'warning')
    flash('A simple info alert—check it out!', 'info')
    flash('A simple light alert—check it out!', 'light')
    flash('A simple dark alert—check it out!', 'dark')
    flash(Markup('A simple success alert with <a href="#" class="alert-link">an example link</a>. Give it a click if you like.'), 'success')
    return render_template('flash.html')


@app.route('/table')
def test_table():
    page = request.args.get('page', 1, type=int)
    pagination = Message.query.paginate(page=page, per_page=10)
    messages = pagination.items
    titles = [('id', '#'), ('text', 'Message'), ('author', 'Author'), ('category', 'Category'), ('draft', 'Draft'), ('create_time', 'Create Time')]
    data = []
    for msg in messages:
        data.append({'id': msg.id, 'text': msg.text, 'author': msg.author, 'category': msg.category, 'draft': msg.draft, 'create_time': msg.create_time})
    return render_template('table.html', messages=messages, titles=titles, Message=Message, data=data)


@app.route('/table/<int:message_id>/view')
def view_message(message_id):
    message = Message.query.get(message_id)
    if message:
        return f'Viewing {message_id} with text "{message.text}". Return to <a href="/table">table</a>.'
    return f'Could not view message {message_id} as it does not exist. Return to <a href="/table">table</a>.'


@app.route('/table/<int:message_id>/edit')
def edit_message(message_id):
    message = Message.query.get(message_id)
    if message:
        message.draft = not message.draft
        db.session.commit()
        return f'Message {message_id} has been editted by toggling draft status. Return to <a href="/table">table</a>.'
    return f'Message {message_id} did not exist and could therefore not be edited. Return to <a href="/table">table</a>.'


@app.route('/table/<int:message_id>/delete', methods=['POST'])
def delete_message(message_id):
    message = Message.query.get(message_id)
    if message:
        db.session.delete(message)
        db.session.commit()
        return f'Message {message_id} has been deleted. Return to <a href="/table">table</a>.'
    return f'Message {message_id} did not exist and could therefore not be deleted. Return to <a href="/table">table</a>.'


@app.route('/table/<int:message_id>/like')
def like_message(message_id):
    return f'Liked the message {message_id}. Return to <a href="/table">table</a>.'


@app.route('/table/new-message')
def new_message():
    return 'Here is the new message page. Return to <a href="/table">table</a>.'


@app.route('/icon')
def test_icon():
    return render_template('icon.html')


@app.route('/icons')
def test_icons():
    return render_template('icons.html')


if __name__ == '__main__':
    app.run(debug=True)
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
