#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from collections import OrderedDict

# from flask import Flask, render_template, send_from_directory, flash, session
from flask import Flask, render_template, request, url_for
import flask_bootstrap
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm, CSRFProtect
from wtforms.fields import *
from wtforms.validators import DataRequired, Length
from sqlalchemy import ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped, mapped_column
import os
import json
import base64
import pprint
import datetime

# from enum import Enum
# from markupsafe import Markup
# from wtforms.validators import DataRequired, Length, Regexp
# from sqlalchemy import Integer, String
# from sqlalchemy import ForeignKey, UniqueConstraint

app = Flask(__name__)
app.secret_key = "dev"
# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
app.config["TESTING"] = True
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///dev.sqlite3"
app.config["SQLALCHEMY_ECHO"] = True
app.config["BOOTSTRAP_BOOTSWATCH_THEME"] = "cyborg"
app.config["BOOTSTRAP_SERVE_LOCAL"] = True
app.config["CHATAPP_NAME"] = "ChatMatch"
app.config["CHATAPP_SHORT_NAME"] = "ChatMatch"
app.config["CHATAPP_TITLE"] = "ChatMatch"
app.config["CHATAPP_DESCRIPTION"] = (
    "App to match discussion participants to topics and timeslots"
)
app.config["CHATAPP_THEME_COLOR"] = "#ff5555"
app.config["CHATAPP_BACKGROUND_COLOR"] = "#5555ff"
app.config["CHATAPP_CSS"] = """
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
    base = os.path.join(
        os.path.dirname(flask_bootstrap.__file__),
        "static",
        "bootstrap5",
        "css",
        "bootswatch",
    )

    themes = OrderedDict()
    themes["default"] = "none"

    for directory in sorted(os.listdir(base)):
        with open(f"{base}/{directory}/_bootswatch.scss") as scss:
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


class User(db.Model):
    __tablename__ = "user_table"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str]
    nick: Mapped[str]
    magic: Mapped[str]
    create_time: Mapped[int]
    edit_time: Mapped[int | None]
    lastuse_time: Mapped[int | None]

    __table_args__ = (
        UniqueConstraint("email"),
        UniqueConstraint("nick"),
    )


class Topic(db.Model):
    __tablename__ = "topic_table"

    id: Mapped[int] = mapped_column(primary_key=True)
    topic: Mapped[str] = mapped_column(unique=True)
    description: Mapped[str | None]
    hidden: Mapped[bool]
    min_users: Mapped[int]
    max_users: Mapped[int]
    creator: Mapped[int] = mapped_column(ForeignKey("user_table.id"))
    create_time: Mapped[int]
    editor: Mapped[int | None] = mapped_column(ForeignKey("user_table.id"))
    edit_time: Mapped[int | None]

    __table_args__ = (UniqueConstraint("topic"),)


class Slot(db.Model):
    __tablename__ = "slot_table"

    id: Mapped[int] = mapped_column(primary_key=True)
    topic: Mapped[int] = mapped_column(ForeignKey("topic_table.id"))
    start_time: Mapped[int]
    duration: Mapped[int]
    creator: Mapped[int] = mapped_column(ForeignKey("user_table.id"))
    create_time: Mapped[int]
    editor: Mapped[int | None] = mapped_column(ForeignKey("user_table.id"))
    edit_time: Mapped[int | None]


class Match(db.Model):
    __tablename__ = "match_table"

    id: Mapped[int] = mapped_column(primary_key=True)
    slot: Mapped[int] = mapped_column(ForeignKey("slot_table.id"))
    user: Mapped[int] = mapped_column(ForeignKey("user_table.id"))
    create_time: Mapped[int]
    confirmed: Mapped[bool]
    confirm_time: Mapped[int | None]
    cancel_time: Mapped[int | None]


with app.app_context():
    # delete database contents
    db.drop_all()

    # create database structures
    db.create_all()

    # system user
    user = User()
    user.email = "system"
    user.nick = "system"
    user.magic = base64.b64encode(os.urandom(32))
    user.create_time = int(datetime.datetime.now().timestamp())
    db.session.add(user)
    db.session.commit()

    # default topic (hideable)
    topic = Topic()
    topic.topic = "Default"
    topic.description = "This is the default topic. Usually not used."
    topic.hidden = False
    topic.min_users = 3
    topic.max_users = 3
    topic.creator = user.id
    topic.create_time = int(datetime.datetime.now().timestamp())
    db.session.add(topic)
    db.session.commit()

    # default slots (hardcoded for 39C3)
    for day in range(27, 30):
        if day == 27:
            mintime = 13
            maxtime = 19
        elif day == 30:
            mintime = 11
            maxtime = 14
        else:
            mintime = 11
            maxtime = 18

        for time in range(mintime, maxtime + 1):
            # first half hour
            slot = Slot()
            slot.topic = topic.id
            slot.start_time = int(
                datetime.datetime(2025, 12, day, time, 0, 0).timestamp()
            )
            slot.duration = 1800
            slot.creator = user.id
            slot.create_time = int(datetime.datetime.now().timestamp())
            db.session.add(slot)

            # second half hour
            if not (day == 27 and time == 19):
                slot = Slot()
                slot.topic = topic.id
                slot.start_time = int(
                    datetime.datetime(2025, 12, day, time, 30, 0).timestamp()
                )
                slot.duration = 1800
                slot.creator = user.id
                slot.create_time = int(datetime.datetime.now().timestamp())
                db.session.add(slot)
        db.session.commit()

    # test match
    match = Match()
    match.slot = 1
    match.user = user.id
    match.create_time = int(datetime.datetime.now().timestamp())
    match.confirmed = False
    db.session.add(match)
    db.session.commit()

    #    - Day 1 (27.12.2025): Slots 1:00pm–7:30pm, selectable every 30 minutes
    #    - Days 2/3 (28./29.12.): 11:00am–7:00pm, every 30 minutes
    #    - Day 4 (30.12.2025): 11:00am–3:00pm, every 30 minutes
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


class RegisterButtonForm(FlaskForm):
    submit = SubmitField()

@app.route("/")
def index():
    return render_template("index.html")


class HelloForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(1, 20)])
    password = PasswordField("Password", validators=[DataRequired(), Length(8, 150)])
    remember = BooleanField(
        "Remember me",
        description="Rember me on my next visit",
        render_kw={"description_class": "fw-bold text-decoration-line-through"},
    )
    submit = SubmitField()


@app.route("/register", methods=["GET", "POST"])
def register():
    form = UserForm()
    if form.validate_on_submit():
        flash("Form validated!")
        return redirect(url_for("index"))
    return render_template(
        "register.html",
        form=form,
    )


class BootswatchForm(FlaskForm):
    """Form to test Bootswatch."""

    # DO NOT EDIT! Use list_bootswatch.py to generate the Radiofield below.
    theme_name = RadioField(
        default="default",
        choices=[
            ("default", "none"),
            ("brite", "Brite 5.3.5"),
            ("cerulean", "Cerulean 5.3.5"),
            ("cosmo", "Cosmo 5.3.5"),
            ("cyborg", "Cyborg 5.3.5"),
            ("darkly", "Darkly 5.3.5"),
            ("flatly", "Flatly 5.3.5"),
            ("journal", "Journal 5.3.5"),
            ("litera", "Litera 5.3.5"),
            ("lumen", "Lumen 5.3.5"),
            ("lux", "Lux 5.3.5"),
            ("materia", "Materia 5.3.5"),
            ("minty", "Minty 5.3.5"),
            ("morph", "Morph 5.3.5"),
            ("pulse", "Pulse 5.3.5"),
            ("quartz", "Quartz 5.3.5"),
            ("sandstone", "Sandstone 5.3.5"),
            ("simplex", "Simplex 5.3.5"),
            ("sketchy", "Sketchy 5.3.5"),
            ("slate", "Slate 5.3.5"),
            ("solar", "Solar 5.3.5"),
            ("spacelab", "Spacelab 5.3.5"),
            ("superhero", "Superhero 5.3.5"),
            ("united", "United 5.3.5"),
            ("vapor", "Vapor 5.3.5"),
            ("yeti", "Yeti 5.3.5"),
            ("zephyr", "Zephyr 5.3.5"),
        ],
    )
    submit = SubmitField()


@app.route("/bootswatch", methods=["GET", "POST"])
def test_bootswatch():
    form = BootswatchForm()
    if form.validate_on_submit():
        if form.theme_name.data == "default":
            app.config["BOOTSTRAP_BOOTSWATCH_THEME"] = None
        else:
            app.config["BOOTSTRAP_BOOTSWATCH_THEME"] = form.theme_name.data
        flash(f"Render style has been set to {form.theme_name.data}.")
    else:
        if app.config["BOOTSTRAP_BOOTSWATCH_THEME"] is not None:
            form.theme_name.data = app.config["BOOTSTRAP_BOOTSWATCH_THEME"]
    return render_template("bootswatch.html", form=form)


@app.route("/table")
def test_table():
    page = request.args.get("page", 1, type=int)
    pagination = Message.query.paginate(page=page, per_page=10)
    messages = pagination.items
    titles = [
        ("id", "#"),
        ("text", "Message"),
        ("author", "Author"),
        ("category", "Category"),
        ("draft", "Draft"),
        ("create_time", "Create Time"),
    ]
    data = []
    for msg in messages:
        data.append(
            {
                "id": msg.id,
                "text": msg.text,
                "author": msg.author,
                "category": msg.category,
                "draft": msg.draft,
                "create_time": msg.create_time,
            }
        )
    return render_template(
        "table.html", messages=messages, titles=titles, Message=Message, data=data
    )


@app.route("/table/<int:message_id>/view")
def view_message(message_id):
    message = Message.query.get(message_id)
    if message:
        return f'Viewing {message_id} with text "{message.text}". Return to <a href="/table">table</a>.'
    return f'Could not view message {message_id} as it does not exist. Return to <a href="/table">table</a>.'

@app.route("/slot/<int:slot_id>")
def slot_form(slot_id):
    slot = Slot.query.get(slot_id)
    if slot:
        return f'Viewing {slot_id} with confirmed "{slot.confirmed}". Return to <a href="/calendar">calendar</a>.'
    return f'Could not view slot {slot_id} as it does not exist. Return to <a href="/calendar">calendar</a>.'

@app.route("/table/<int:message_id>/edit")
def edit_message(message_id):
    message = Message.query.get(message_id)
    if message:
        message.draft = not message.draft
        db.session.commit()
        return f'Message {message_id} has been editted by toggling draft status. Return to <a href="/table">table</a>.'
    return f'Message {message_id} did not exist and could therefore not be edited. Return to <a href="/table">table</a>.'


@app.route("/table/<int:message_id>/delete", methods=["POST"])
def delete_message(message_id):
    message = Message.query.get(message_id)
    if message:
        db.session.delete(message)
        db.session.commit()
        return f'Message {message_id} has been deleted. Return to <a href="/table">table</a>.'
    return f'Message {message_id} did not exist and could therefore not be deleted. Return to <a href="/table">table</a>.'


@app.route("/table/<int:message_id>/like")
def like_message(message_id):
    return f'Liked the message {message_id}. Return to <a href="/table">table</a>.'


@app.route("/table/new-message")
def new_message():
    return 'Here is the new message page. Return to <a href="/table">table</a>.'


@app.route("/topics")
def topics():
    return render_template("topics.html")


@app.route("/calendar")
def calendar():
    # get topic argument from URL
    topic_id = request.args.get("topic", 1, type=int)

    # fetch Matches for Slots
    match_rows = db.session.execute(
        db.select(Match).where(Match.slot == Slot.id, Slot.topic == topic_id)
    )
    if app.debug and 0:
        print(topic_id)
        pprint.pp(match_rows)

    # prepare matches
    matches = dict()
    for row in match_rows:
        if app.debug and 1:
            pprint.pp(row)
            pprint.pp(type(row.Match))
            pprint.pp(row.Match.__dict__)
        if row.Match.slot not in matches:
            matches[row.Match.slot] = dict()
            matches[row.Match.slot]["matched"] = 0
            matches[row.Match.slot]["confirmed"] = 0
            matches[row.Match.slot]["cancelled"] = 0
        matches[row.Match.slot]["matched"] += 1
        matches[row.Match.slot]["confirmed"] += 1 if row.Match.confirmed else 0
        matches[row.Match.slot]["cancelled"] += 1 if row.Match.cancel_time else 0

    if app.debug and 1:
        pprint.pp(matches)

    # fetch Slots and Topic
    slot_rows = db.session.execute(
        db.select(Slot, Topic).where(Slot.topic == Topic.id, Topic.id == topic_id)
    )
    if app.debug and 0:
        print(topic_id)
        pprint.pp(slot_rows)

    # collect data for calendar view
    days = dict()
    slots = dict()
    topic = Topic()
    for row in slot_rows:
        if app.debug and 0:
            pprint.pp(row)
            pprint.pp(type(row.Slot))
            pprint.pp(row.Slot.__dict__)
            pprint.pp(type(row.Topic))
            pprint.pp(row.Topic.__dict__)

        # this will override the higher scope variable all of the time
        topic = row.Topic

        start_time = datetime.datetime.fromtimestamp(row.Slot.start_time)
        end_time = start_time + datetime.timedelta(seconds=row.Slot.duration)
        day = start_time.strftime("%Y%m%d")

        if app.debug and 0:
            pprint.pp(start_time)
            pprint.pp(end_time)
            pprint.pp(day)

        if not day in days:
            days[day] = dict()
        slot = "%s - %s" % (start_time.strftime("%H:%M"), end_time.strftime("%H:%M"))
        if slot not in slots:
            slots[slot] = 0
        else:
            slots[slot] += 1

        # construct slot cell entry
        matched = 0
        confirmed = 0
        cancelled = 0
        if row.Slot.id in matches:
            matched = matches[row.Slot.id]["matched"]
            confirmed = matches[row.Slot.id]["confirmed"]
            cancelled = matches[row.Slot.id]["cancelled"]

        days[day][slot] = "<a href=\"%s\">%d/%d, %d confirmed</a>" % (
            url_for("slot_form", slot_id=row.Slot.id),
            matched - cancelled,
            topic.min_users,
            confirmed
        )

    # create headings
    titles = [("slot", "Slot")]
    safe_columns = []
    for day in days.keys():
        titles.append(
            (day, datetime.datetime.strptime(day, "%Y%m%d").strftime("%d.%m.%Y"))
        )
        safe_columns.append(day)

    if app.debug:
        pprint.pp(titles)
        pprint.pp(days)

    # pivot data into calendar structure
    calendar = []
    for slot in dict(sorted(slots.items())):
        entry = dict()
        entry["slot"] = slot
        for day, dayslots in days.items():
            if slot in dayslots:
                entry[day] = dayslots[slot]
        if app.debug and 0:
            pprint.pp(entry)
        calendar.append(entry)

    # render calendar
    return render_template(
        "calendar.html",
        titles=titles,
        calendar=calendar,
        topic_title=topic.topic,
        topic_description=topic.description,
        safe_columns=safe_columns
    )


@app.route("/admin")
def admin():
    return render_template("admin.html")


@app.route("/site.webmanifest")
def site_webmanifest():
    return render_template("site.webmanifest")


@app.route("/favicon.ico")
def favicon():
    return send_from_directory("static", "favicon.ico")


if __name__ == "__main__":
    app.run(debug=True)
