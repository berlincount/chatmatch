#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from collections import OrderedDict

# from flask import Flask, render_template, send_from_directory, flash, session
from flask import (
    Flask,
    render_template,
    request,
    url_for,
    flash,
    redirect,
    request,
    jsonify,
)
import flask_bootstrap
from flask_sqlalchemy import SQLAlchemy
from flask_session import Session
from flask_wtf import FlaskForm, CSRFProtect
from wtforms.fields import *
from wtforms.widgets import html_params
from wtforms.validators import DataRequired, Length
from sqlalchemy import ForeignKey, UniqueConstraint, func
from sqlalchemy.exc import IntegrityError, PendingRollbackError
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped, mapped_column
from cachelib.file import FileSystemCache
from functools import lru_cache
import os
import json
import base64
import pprint
import datetime
import smtplib
import ssl

# from enum import Enum
# from markupsafe import Markup
# from wtforms.validators import DataRequired, Length, Regexp
# from sqlalchemy import Integer, String
# from sqlalchemy import ForeignKey, UniqueConstraint


def get_config(key):
    global app
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


class ChatMatch(DeclarativeBase):
    pass


class User(ChatMatch):
    __tablename__ = "user_table"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str]
    nickname: Mapped[str]
    magic: Mapped[str]
    newmagic: Mapped[str | None]
    create_time: Mapped[int]
    edit_time: Mapped[int | None]
    lastuse_time: Mapped[int | None]

    __table_args__ = (
        UniqueConstraint("email"),
        UniqueConstraint("nickname"),
    )


class Topic(ChatMatch):
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


class Slot(ChatMatch):
    __tablename__ = "slot_table"

    id: Mapped[int] = mapped_column(primary_key=True)
    topic: Mapped[int] = mapped_column(ForeignKey("topic_table.id"))
    start_time: Mapped[int]
    duration: Mapped[int]
    creator: Mapped[int] = mapped_column(ForeignKey("user_table.id"))
    create_time: Mapped[int]
    editor: Mapped[int | None] = mapped_column(ForeignKey("user_table.id"))
    edit_time: Mapped[int | None]

    __table_args__ = (UniqueConstraint("start_time", "topic"),)


class Match(ChatMatch):
    __tablename__ = "match_table"

    id: Mapped[int] = mapped_column(primary_key=True)
    slot: Mapped[int] = mapped_column(ForeignKey("slot_table.id"))
    user: Mapped[int] = mapped_column(ForeignKey("user_table.id"))
    create_time: Mapped[int]
    confirmed: Mapped[bool]
    edit_time: Mapped[int | None]
    confirm_time: Mapped[int | None]
    cancel_time: Mapped[int | None]

    __table_args__ = (UniqueConstraint("slot", "user"),)


class RegisterButtonForm(FlaskForm):
    submit = SubmitField()


class HelloForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(1, 20)])
    password = PasswordField("Password", validators=[DataRequired(), Length(8, 150)])
    remember = BooleanField(
        "Remember me",
        description="Rember me on my next visit",
        render_kw={"description_class": "fw-bold text-decoration-line-through"},
    )
    submit = SubmitField()


@lru_cache(maxsize=16)
def fetch_topics():
    global db
    topics = db.session.execute(
        db.select(Topic).where(Topic.hidden == False).order_by(Topic.id)
    )

    choices = []
    for row in topics:
        choices.append((row.Topic.id, row.Topic.topic))

    return choices


@lru_cache(maxsize=16)
def fetch_slots(topic_id):
    # fetch Slots and Topic
    slot_rows = db.session.execute(
        db.select(Slot, Topic).where(Slot.topic == Topic.id, Topic.id == topic_id)
    )

    # collect data for calendar view
    days = dict()
    slots = dict()
    topic = Topic()
    for row in slot_rows:
        # this will override the higher scope variable all of the time
        topic = row.Topic

        now = datetime.datetime.now()
        start_time = datetime.datetime.fromtimestamp(row.Slot.start_time)
        end_time = start_time + datetime.timedelta(seconds=row.Slot.duration)
        day = start_time.strftime("%Y%m%d")

        if not day in days:
            days[day] = dict()
        slot = "%s-%s" % (start_time.strftime("%H:%M"), end_time.strftime("%H:%M"))
        if slot not in slots:
            slots[slot] = 0
        else:
            slots[slot] += 1

        days[day][slot] = True if start_time > now else False

    # pivot data into calendar structure
    calendar = []
    for slot in dict(sorted(slots.items())):
        entry = dict()
        entry["slot"] = slot
        for day, dayslots in days.items():
            if slot in dayslots:
                entry[day] = dayslots[slot]
        calendar.append(entry)

    # row headings
    titles = [("slot", "Slot")]
    for day in days.keys():
        titles.append(
            (day, datetime.datetime.strptime(day, "%Y%m%d").strftime("%d.%m."))
        )

    # convert to choices structure
    choices = [(titles, "titles")]
    for entry in calendar:
        slot = entry["slot"]
        del entry["slot"]
        choices.append((entry, slot))

    return choices


def index():
    global db

    def chatmatch_calendar_widget(field, ul_class="", **kwargs):
        kwargs.setdefault("type", "checkbox")
        field_id = kwargs.pop("id", field.id)
        # html = ['<ul %s>' % html_params(id=field_id, class_=ul_class)]
        html = [
            '<div class="tables-responsive-sm">\n<table class="table table-striped" %s>\n'
            % html_params(id=field_id, class_=ul_class)
        ]
        titles = None
        body = None
        for values, label, checked, render_kw in field.iter_choices():
            if not titles and label == "titles":
                titles = values
                html.append('<thead class="thead-dark">\n <tr>\n')
                for title in titles:
                    html.append('  <th scope="col">%s</th>\n' % title[1])
                html.append(" </tr>\n</thead>")
                continue
            if not body:
                body = True
                html.append('<tbody class="table-group-divider">\n')

            html.append(" <tr>\n")
            for idx, title in enumerate(titles):
                if idx == 0:
                    html.append("  <td>%s</td>\n" % label)
                else:
                    if title[0] in values.keys():
                        choice_id = "%s-%s-%s" % (field_id, title[0], label)
                        if "class" in kwargs:
                            del kwargs["class"]
                        if not values[title[0]]:
                            kwargs["disabled"] = "disabled"
                        else:
                            if "disabled" in kwargs:
                                del kwargs["disabled"]
                        options = dict(kwargs, name=choice_id, id=choice_id)
                        html.append(
                            "  <td><input %s /></td>\n" % html_params(**options)
                        )
                    else:
                        html.append("  <td></td>\n")

            # for idx,value in values.items():
            #  pprint.pp('value')
            #  pprint.pp(value)
            #  choice_id = '%s-%s-%s' % (field_id, label, value)
            #  options = dict(kwargs, name=field.name, value=value, id=choice_id)
            #  if checked:
            #    options['checked'] = 'checked'
            #  html.append('<td> %d %s </td>' % (idx,html_params(**options)))
            html.append(" </tr>\n")
        if body:
            html.append("</tbody>\n")
        html.append("</table>\n</div>")
        return "".join(html)

    class MainForm(FlaskForm):
        """Our main form."""

        nickname = StringField(description="Your nickname. Will be visible to others")
        email = EmailField(
            description="Your email address. Will be used to send you notifications, and nothing else"
        )

        # Topics
        topic = SelectField(choices=fetch_topics())

        # Slots
        slots = SelectMultipleField(
            # FIXME slots are loaded from first, hidden topic
            choices=fetch_slots(1),
            widget=chatmatch_calendar_widget,
        )

        submit = SubmitField()

    form = MainForm()
    if form.validate_on_submit():
        formdict = request.form.to_dict()
        # try to load user
        users = db.session.execute(
            db.select(User)
            .where(User.nickname == formdict["nickname"])
            .where(User.email == formdict["email"])
        ).all()
        # create user if it doesn't exist
        if not len(users):
            try:
                user = User()
                user.nickname = formdict["nickname"]
                user.email = formdict["email"]
                user.magic = base64.b64encode(os.urandom(32))
                user.create_time = int(datetime.datetime.now().timestamp())
                db.session.add(user)
                db.session.commit()
            except IntegrityError:
                print("❎ DUPLICATE USER %s" % formdict["nickname"])
                flash(
                    "Either the nickname or the email address exist already - and don't match! Sorry.",
                    "danger",
                )
                return redirect(url_for("index"))
            print("✅ ADD USER %s" % formdict["nickname"])

            # load users again
            users = db.session.execute(
                db.select(User)
                .where(User.nickname == formdict["nickname"])
                .where(User.email == formdict["email"])
            ).all()

        # try to load topic
        topics = db.session.execute(
            db.select(Topic).where(Topic.id == int(formdict["topic"]))
        ).all()
        if len(topics) != 1:
            flash(
                "Something went wrong finding the topic! Sorry.",
                "danger",
            )
            return redirect(url_for("index"))

        # try to load user's slots
        matches = db.session.execute(
            db.select(Match).where(Match.user == users[0].User.id)
        ).all()
        matchslots = dict()
        for row in matches:
            matchslots[row.Match.slot] = row.Match
        if app.debug:
            pprint.pp("matchslots")
            pprint.pp(matchslots)

        # try to load all slots
        slots = db.session.execute(
            db.select(Slot).where(Slot.topic == topics[0].Topic.id)
        ).all()

        # Do we need to recalc the Matches?
        recalc = False
        # check all slots
        if app.debug:
            pprint.pp(formdict)
        for row in slots:
            slotstart = datetime.datetime.fromtimestamp(row.Slot.start_time)
            slotend = slotstart + datetime.timedelta(seconds=row.Slot.duration)
            slotname = "slots-%s-%s" % (
                slotstart.strftime("%Y%m%d-%H:%M"),
                slotend.strftime("%H:%M"),
            )

            if slotname in formdict:
                if row.Slot.id in matchslots.keys():
                    if not matchslots[row.Slot.id].cancel_time:
                        print("✅ EXISTING MATCH %s" % slotname)
                    else:
                        print("✅ UNCANCEL MATCH %s" % slotname)
                        db.session.query(Match).filter(
                            Match.id == matchslots[row.Slot.id].id
                        ).update(
                            {
                                "confirmed": False,
                                "confirm_time": None,
                                "edit_time": int(datetime.datetime.now().timestamp()),
                                "cancel_time": None,
                            }
                        )
                        recalc = True
                else:
                    print("✅ ADD MATCH %s" % slotname)
                    match = Match()
                    match.slot = row.Slot.id
                    match.user = users[0].User.id
                    match.create_time = int(datetime.datetime.now().timestamp())
                    match.confirmed = False
                    match.cancel_time = None
                    db.session.add(match)
                    recalc = True

            elif row.Slot.id in matchslots.keys():
                print("✅ CANCEL MATCH %s" % slotname)
                db.session.query(Match).filter(
                    Match.id == matchslots[row.Slot.id].id
                ).update(
                    {
                        "confirmed": False,
                        "edit_time": int(datetime.datetime.now().timestamp()),
                        "cancel_time": int(datetime.datetime.now().timestamp()),
                    }
                )
                recalc = True

        db.session.commit()

        # class Slot(ChatMatch):
        #     __tablename__ = "slot_table"
        #
        #     id: Mapped[int] = mapped_column(primary_key=True)
        #     topic: Mapped[int] = mapped_column(ForeignKey("topic_table.id"))
        #     start_time: Mapped[int]
        #     duration: Mapped[int]
        #     creator: Mapped[int] = mapped_column(ForeignKey("user_table.id"))
        #     create_time: Mapped[int]
        #     editor: Mapped[int | None] = mapped_column(ForeignKey("user_table.id"))
        #     edit_time: Mapped[int | None]

        # class Match(ChatMatch):
        #    __tablename__ = "match_table"
        #
        #    id: Mapped[int] = mapped_column(primary_key=True)
        #    slot: Mapped[int] = mapped_column(ForeignKey("slot_table.id"))
        #    user: Mapped[int] = mapped_column(ForeignKey("user_table.id"))
        #    create_time: Mapped[int]
        #    confirmed: Mapped[bool]
        #    confirm_time: Mapped[int | None]
        #    cancel_time: Mapped[int | None]

        flash(
            "Form submitted! Thanks! You will get a confirmation email. Feel free to submit another form!",
            "success",
        )
        send_topic_mail(users[0].User, topics[0].Topic)

        if recalc:
            recalc_topic(topics[0].Topic.id)

        return redirect(url_for("index"))

    return render_template("index.html", form=form)


def recalc_all_topics():
    topics = db.session.execute(
        db.select(Topic).where(Topic.hidden == False).order_by(Topic.id)
    )
    results = dict()
    for row in topics:
        results[row.Topic.id] = recalc_topic(row.Topic.id)

    return jsonify(results)


def recalc_topic(topic_id):
    global db

    print("✅ RECALC TOPIC %d" % topic_id)

    # try to load topic
    topics = db.session.execute(db.select(Topic).where(Topic.id == topic_id)).all()
    if len(topics) != 1:
        print(
            "❎❎❎ RECALC TOPIC %d FAILURE - Not exactly one topic found?" % topic_id
        )
        return False
    topic = topics[0].Topic

    # try to load slots
    slots = db.session.execute(
        db.select(Slot).where(Slot.topic == topics[0].Topic.id)
    ).all()
    if not len(slots):
        print("❎❎❎ RECALC TOPIC %d FAILURE - No slots found?" % topic_id)
        return False

    # try to load matches
    matches = db.session.execute(
        db.select(Match, Slot)
        .filter(Match.slot == Slot.id)
        .filter(Slot.topic == topic_id)
        .order_by(Match.slot, Slot.start_time, Match.create_time)
    ).all()
    if not len(matches):
        print("❎❎❎ RECALC TOPIC %d UNSUCCESSFUL - No matches found?" % topic_id)
        return False
    else:
        print("✅ RECALC TOPIC %d - %d matches" % (topic_id, len(matches)))

        now = int(datetime.datetime.now().timestamp())

        # collect matches by slot
        matchslots = dict()
        slot_id = None
        for match, slot in matches:
            # skip slots already past/started
            if slot.start_time <= now:
                continue

            if slot_id != slot.id:
                matchslots[slot.id] = []
                slot_id = slot.id
            if not match.cancel_time:
                matchslots[slot.id].append(match)

        # check whether we need to confirm
        for slot_id in matchslots.keys():
            if len(matchslots[slot_id]) >= topic.min_users:
                confirm_previous = []
                confirm_pending = []
                for match in matchslots[slot_id]:
                    if match.confirmed:
                        confirm_previous.append(match.id)
                    else:
                        if (
                            len(confirm_previous) + len(confirm_pending)
                        ) < topic.max_users:
                            print(
                                "✅✅ RECALC TOPIC %d: Mail user %d about slot %d"
                                % (topic_id, match.user, slot_id)
                            )
                            confirm_pending.append(match.id)

                send_slot_mail(slot, topic, confirm_previous, confirm_pending)

    return True


def send_topic_mail(user, topic):
    global db
    slots = db.session.execute(
        db.select(Match, Slot)
        .filter(Match.slot == Slot.id)
        .filter(Slot.topic == topic.id)
        .order_by(Match.slot, Slot.start_time, Match.create_time)
    ).all()

    message = """From: Relationship Geeks Matching Service
Subject: You've signed up for a conversation

Hi Relationship Geek!

You've signed up for a conversation about %s for the following time slots:

""" % ('"' + topic.topic + '"',)

    slot_id = None
    for match, slot in slots:
        if slot.id != slot_id:
            slot_id = slot.id
            start_time = datetime.datetime.fromtimestamp(slot.start_time)
            end_time = start_time + datetime.timedelta(seconds=slot.duration)
            message += "%s-%s\n" % (
                start_time.strftime("%d.%m.%Y %H:%M"),
                end_time.strftime("%H:%M"),
            )

    message += """
As soon as at least %d (max %d) people have signed up for a conversation about this topic for one of the time above time slots we'll send you another message to confirm the conversation is happening!

If nobody signs up for the same topic & time slot you won't receive further messages.
""" % (topic.min_users, topic.max_users)

    if app.debug:
        print("RECIPIENT")
        print(user.email)
        print("STARTMESSAGE")
        print(message)
        print("ENDMESSAGE")
    else:
        send_mail(user.email, message)


def send_slot_mail(slot, topic, confirm_previous, confirm_pending):
    global db
    users = db.session.execute(
        db.select(User, Match)
        .filter(Match.slot == slot.id)
        .filter(User.id == Match.user)
        .order_by(User.nickname)
    ).all()

    if not len(users):
        print("❎❎❎ SLOT MAIL %d UNSUCCESSFUL - No users found?" % slot.id)
        return False

    now = int(datetime.datetime.now().timestamp())

    # collect nicknames
    nicknames = []
    for user, match in users:
        if match.id in confirm_previous or match.id in confirm_pending:
            nicknames.append(user.nickname)
    if app.debug:
        pprint.pp(nicknames)

    message = """From: Relationship Geeks Matching Service
Subject: Conversation matched!

Hi Relationship Geek!

You've signed up for a conversation about %s, and we've found matches!

""" % ('"' + topic.topic + '"',)

    message += "Timeslot: "

    start_time = datetime.datetime.fromtimestamp(slot.start_time)
    end_time = start_time + datetime.timedelta(seconds=slot.duration)
    message += "%s-%s\n" % (
        start_time.strftime("%d.%m.%Y %H:%M"),
        end_time.strftime("%H:%M"),
    )

    message += """
You will be meeting with the following list of people at the Relationship Geeks assembly - please find a spot to discuss at by yourself:

"""
    message += "\n".join(nicknames)
    message += """

Have a lot of fun!
"""

    for user, match in users:
        if match.id in confirm_pending and not match.confirmed:
            if app.debug:
                print("RECIPIENT")
                print(user.email)
                print("STARTMESSAGE")
                print(message)
                print("ENDMESSAGE")
            else:
                send_mail(recipient, message)

                db.session.query(Match).filter(Match.id == match.id).update(
                    {
                        "confirmed": True,
                        "confirm_time": now,
                        "edit_time": now,
                        "cancel_time": None,
                    }
                )
    db.session.commit()


def register():
    form = UserForm()
    if form.validate_on_submit():
        flash("Form validated!")
        return redirect(url_for("index"))
    return render_template(
        "register.html",
        form=form,
    )


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


def view_message(message_id):
    message = Message.query.get(message_id)
    if message:
        return f'Viewing {message_id} with text "{message.text}". Return to <a href="/table">table</a>.'
    return f'Could not view message {message_id} as it does not exist. Return to <a href="/table">table</a>.'


def slot_form(slot_id):
    slot = Slot.query.get(slot_id)
    if slot:
        return f'Viewing {slot_id} with confirmed "{slot.confirmed}". Return to <a href="/calendar">calendar</a>.'
    return f'Could not view slot {slot_id} as it does not exist. Return to <a href="/calendar">calendar</a>.'


def edit_message(message_id):
    global db
    message = Message.query.get(message_id)
    if message:
        message.draft = not message.draft
        db.session.commit()
        return f'Message {message_id} has been editted by toggling draft status. Return to <a href="/table">table</a>.'
    return f'Message {message_id} did not exist and could therefore not be edited. Return to <a href="/table">table</a>.'


def delete_message(message_id):
    global db
    message = Message.query.get(message_id)
    if message:
        db.session.delete(message)
        db.session.commit()
        return f'Message {message_id} has been deleted. Return to <a href="/table">table</a>.'
    return f'Message {message_id} did not exist and could therefore not be deleted. Return to <a href="/table">table</a>.'


def like_message(message_id):
    return f'Liked the message {message_id}. Return to <a href="/table">table</a>.'


def new_message():
    return 'Here is the new message page. Return to <a href="/table">table</a>.'


def topics():
    return render_template("topics.html")


def calendar():
    global app, db
    # get topic argument from URL
    topic_id = request.args.get("topic", 1, type=int)

    # fetch Matches for Slots
    match_rows = db.session.execute(
        db.select(Match).where(Match.slot == Slot.id, Slot.topic == topic_id)
    )
    if app.debug and 0:
        pprint.pp(topic_id)
        pprint.pp(match_rows)

    # prepare matches
    matches = dict()
    for row in match_rows:
        if app.debug and 0:
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

    if app.debug and 0:
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
        slot = "%s-%s" % (start_time.strftime("%H:%M"), end_time.strftime("%H:%M"))
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

        days[day][slot] = '<a href="%s">%d/%d, %d confirmed</a>' % (
            url_for("slot_form", slot_id=row.Slot.id),
            matched - cancelled,
            topic.min_users,
            confirmed,
        )

    # create headings
    titles = [("slot", "Slot")]
    safe_columns = []
    for day in days.keys():
        titles.append(
            (day, datetime.datetime.strptime(day, "%Y%m%d").strftime("%d.%m.%Y"))
        )
        safe_columns.append(day)

    if app.debug and 0:
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
        safe_columns=safe_columns,
    )


def admin():
    return render_template("admin.html")


def site_webmanifest():
    return render_template("site.webmanifest")


def favicon():
    return send_from_directory("static", "favicon.ico")


def send_mail(recipient, message):
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(
        os.getenv("SMTP_SERVER", "localhost"),
        int(os.getenv("SMTP_PORT", "465")),
        context=context,
    ) as server:
        server.login(
            os.getenv("SMTP_USERNAME", "username@domain"),
            os.getenv("SMTP_PASSWORD", "password"),
        )
        return server.sendmail(
            os.getenv("SMTP_USERNAME", "username@domain"), recipient, message
        )


def create_app(test_config=None, debug=False):
    global app, bootstrap, db, session
    ## create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY", "dev"),
        TESTING=bool(os.getenv("TESTING", os.getenv("DEBUG"))),
        SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URI", "sqlite:///dev.sqlite3"),
        SQLALCHEMY_ECHO=bool(os.getenv("DATABASE_ECHO", os.getenv("DEBUG"))),
        BOOTSTRAP_BOOTSWATCH_THEME=os.getenv("THEME", "pulse"),
        BOOTSTRAP_SERVE_LOCAL=True,
        SESSION_TYPE="cachelib",
        SESSION_SERIALIZATION_FORMAT="json",
        SESSION_CACHELIB=FileSystemCache(
            threshold=500, cache_dir=os.getenv("SESSION_DIR", "sessions")
        ),
        CHATMATCH_NAME=os.getenv("CHATMATCH_NAME", "ChatMatch"),
        CHATMATCH_SHORT_NAME=os.getenv(
            "CHATMATCH_SHORT_NAME", os.getenv("CHATMATCH_NAME", "ChatMatch")
        ),
        CHATMATCH_TITLE=os.getenv("CHATMATCH_TITLE", "ChatMatch"),
        CHATMATCH_THEME_COLOR=os.getenv("CHATMATCH_THEME_COLOR", "#ff5555"),
        CHATMATCH_BACKGROUND_COLOR=os.getenv("CHATMATCH_BACKGROUND_COLOR", "#5555ff"),
    )
    app.config["CHATMATCH_DESCRIPTION"] = os.getenv(
        "CHATMATCH_DESCRIPTION",
        "App to match discussion participants to topics and timeslots",
    )
    app.config["CHATMATCH_CSS"] = """
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
    bootstrap = flask_bootstrap.Bootstrap5(app)
    db = SQLAlchemy(app, model_class=ChatMatch)
    app.jinja_env.globals.update(get_config=get_config, list_themes=list_themes)
    csrf = CSRFProtect(app)
    session = Session(app)

    app.add_url_rule("/", "index", index, methods=["GET", "POST"])
    app.add_url_rule("/recalc_all_topics", "recalc_all_topics", recalc_all_topics)
    # app.add_url_rule("/register", "register", register, methods=["GET", "POST"])
    # app.add_url_rule("/table", "test_table", test_table)
    # app.add_url_rule("/table/<int:message_id>/view", "view_message", view_message)
    # app.add_url_rule("/slot/<int:slot_id>", "slot_form", slot_form)
    # app.add_url_rule("/table/<int:message_id>/edit", "edit_message", edit_message)
    # app.add_url_rule( "/table/<int:message_id>/delete", "delete_message", delete_message, methods=["POST"],)
    # app.add_url_rule("/table/<int:message_id>/like", "like_message", like_message)
    # app.add_url_rule("/table/new-message", "new_message", new_message)
    # app.add_url_rule("/topics", "topics", topics)
    # app.add_url_rule("/calendar", "calendar", calendar)
    app.add_url_rule("/admin", "admin", admin)
    app.add_url_rule("/site.webmanifest", "site_webmanifest", site_webmanifest)
    app.add_url_rule("/favicon.ico", "favicon", favicon)

    with app.app_context():
        # delete database contents
        if bool(os.getenv("DANGER_DROP_DATABASE")):
            db.drop_all()

        # create database structures
        try:
            db.create_all()
        except IntegrityError, PendingRollbackError:
            pass

        # system user
        try:
            user = User()
            user.email = "system"
            user.nickname = "system"
            user.magic = base64.b64encode(os.urandom(32))
            user.create_time = int(datetime.datetime.now().timestamp())
            db.session.add(user)
            db.session.commit()
        except IntegrityError, PendingRollbackError:
            db.session.rollback()
            pass

        # default topic (hideable)
        try:
            topic = Topic()
            topic.topic = "Default"
            topic.description = "This is the default topic. Usually not used."
            topic.hidden = True
            topic.min_users = 3
            topic.max_users = 5
            topic.creator = user.id
            topic.create_time = int(datetime.datetime.now().timestamp())
            db.session.add(topic)

            topic = Topic()
            topic.topic = "Poly with (planned) kids"
            topic.hidden = False
            topic.min_users = 3
            topic.max_users = 5
            topic.creator = user.id
            topic.create_time = int(datetime.datetime.now().timestamp())
            db.session.add(topic)

            topic = Topic()
            topic.topic = "Jealousy"
            topic.hidden = False
            topic.min_users = 3
            topic.max_users = 5
            topic.creator = user.id
            topic.create_time = int(datetime.datetime.now().timestamp())
            db.session.add(topic)

            topic = Topic()
            topic.topic = "Transitioning to Relationship Anarchy"
            topic.hidden = False
            topic.min_users = 3
            topic.max_users = 5
            topic.creator = user.id
            topic.create_time = int(datetime.datetime.now().timestamp())
            db.session.add(topic)

            topic = Topic()
            topic.topic = "Sex, safety and transparency"
            topic.hidden = False
            topic.min_users = 3
            topic.max_users = 5
            topic.creator = user.id
            topic.create_time = int(datetime.datetime.now().timestamp())
            db.session.add(topic)

            topic = Topic()
            topic.topic = "Organizing calendars and time limitations"
            topic.hidden = False
            topic.min_users = 3
            topic.max_users = 5
            topic.creator = user.id
            topic.create_time = int(datetime.datetime.now().timestamp())
            db.session.add(topic)

            topic = Topic()
            topic.topic = "Cohabitation"
            topic.hidden = False
            topic.min_users = 3
            topic.max_users = 5
            topic.creator = user.id
            topic.create_time = int(datetime.datetime.now().timestamp())
            db.session.add(topic)

            db.session.commit()
        except IntegrityError, PendingRollbackError:
            db.session.rollback()
            pass

        # default slots (hardcoded for 39C3)
        maxtopic = db.session.query(func.max(Topic.id)).all()[0][0]
        for topic in range(1, maxtopic + 1):
            try:
                for day in range(27, 30 + 1):
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
                        slot.topic = topic
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
                            slot.topic = topic
                            slot.start_time = int(
                                datetime.datetime(
                                    2025, 12, day, time, 30, 0
                                ).timestamp()
                            )
                            slot.duration = 1800
                            slot.creator = user.id
                            slot.create_time = int(datetime.datetime.now().timestamp())
                            db.session.add(slot)
                    db.session.commit()
            except IntegrityError, PendingRollbackError:
                db.session.rollback()
                pass

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
        #     db.session.commit()

    return app


if __name__ == "__main__":
    global app
    app = create_app()
    app.run(debug=bool(os.getenv("DEBUG")))
