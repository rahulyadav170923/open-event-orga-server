import inspect
import json
import logging
import os
from datetime import datetime

from flask import request, url_for, flash
from flask.ext.restplus import abort
from flask.ext import login
from flask_admin import BaseView, expose
from markupsafe import Markup
from werkzeug.utils import redirect, secure_filename

from app.helpers.data import DataManager
from app.models.call_for_papers import CallForPaper
from ...helpers.data_getter import DataGetter


def get_published_event_or_abort(event_id):
    event = DataGetter.get_event(event_id=event_id)
    if not event or event.state != u'Published':
        user = login.current_user
        if not login.current_user.is_authenticated or (not user.is_organizer(event_id) and not
                                                       user.is_coorganizer(event_id) and not
                                                       user.is_track_organizer(event_id)):
            abort(404)

    if event.in_trash:
        abort(404)
    return event


class EventDetailView(BaseView):

    @expose('/')
    def display_default(self):
        return redirect("/browse")

    @expose('/<int:event_id>/')
    def display_event_detail_home(self, event_id):
        event = get_published_event_or_abort(event_id)
        placeholder_images = DataGetter.get_event_default_images()
        call_for_speakers = DataGetter.get_call_for_papers(event_id).first()
        accepted_sessions = DataGetter.get_sessions(event_id)
        if event.copyright:
            licence_details = DataGetter.get_licence_details(event.copyright.licence)
        else:
            licence_details = None

        module = DataGetter.get_module()
        tickets = DataGetter.get_sales_open_tickets(event_id)
        return self.render('/gentelella/guest/event/details.html',
                           event=event,
                           placeholder_images=placeholder_images,
                           accepted_sessions=accepted_sessions,
                           call_for_speakers=call_for_speakers,
                           licence_details=licence_details,
                           module=module,
                           tickets=tickets if tickets else [])

    @expose('/<int:event_id>/sessions/')
    def display_event_sessions(self, event_id):
        event = get_published_event_or_abort(event_id)
        placeholder_images = DataGetter.get_event_default_images()
        if not event.has_session_speakers:
            abort(404)
        call_for_speakers = DataGetter.get_call_for_papers(event_id).first()
        tracks = DataGetter.get_tracks(event_id)
        accepted_sessions = DataGetter.get_sessions(event_id)
        if not accepted_sessions:
            abort(404)
        return self.render('/gentelella/guest/event/sessions.html', event=event,
                           placeholder_images=placeholder_images, accepted_sessions=accepted_sessions, tracks=tracks, call_for_speakers=call_for_speakers)

    @expose('/<int:event_id>/schedule/')
    def display_event_schedule(self, event_id):
        event = get_published_event_or_abort(event_id)
        placeholder_images = DataGetter.get_event_default_images()
        if not event.has_session_speakers:
            abort(404)
        tracks = DataGetter.get_tracks(event_id)
        accepted_sessions = DataGetter.get_sessions(event_id)
        if not accepted_sessions or not event.schedule_published_on:
            abort(404)
        return self.render('/gentelella/guest/event/schedule.html', event=event,
                           placeholder_images=placeholder_images, accepted_sessions=accepted_sessions, tracks=tracks)

    @expose('/<int:event_id>/cfs/', methods=('GET',))
    def display_event_cfs(self, event_id, via_hash=False):
        event = get_published_event_or_abort(event_id)
        placeholder_images = DataGetter.get_event_default_images()
        if not event.has_session_speakers:
            abort(404)

        call_for_speakers = DataGetter.get_call_for_papers(event_id).first()
        accepted_sessions = DataGetter.get_sessions(event_id)

        if not call_for_speakers or (not via_hash and call_for_speakers.privacy == 'private'):
            abort(404)

        form_elems = DataGetter.get_custom_form_elements(event_id)
        speaker_form = json.loads(form_elems.speaker_form)
        session_form = json.loads(form_elems.session_form)

        now = datetime.now()
        state = "now"
        if call_for_speakers.end_date < now:
            state = "past"
        elif call_for_speakers.start_date > now:
            state = "future"
        speakers = DataGetter.get_speakers(event_id).all()
        return self.render('/gentelella/guest/event/cfs.html', event=event, accepted_sessions=accepted_sessions, speaker_form=speaker_form,
                           session_form=session_form, call_for_speakers=call_for_speakers,
                           placeholder_images=placeholder_images, state=state, speakers=speakers, via_hash=via_hash)

    @expose('/cfs/<hash>', methods=('GET',))
    def display_event_cfs_via_hash(self, hash):
        call_for_speakers = CallForPaper.query.filter_by(hash=hash).first()
        if not call_for_speakers:
            abort(404)
        return self.display_event_cfs(call_for_speakers.event_id, True)

    @expose('/<int:event_id>/cfs/', methods=('POST',))
    def process_event_cfs(self, event_id):
        email = request.form['email']
        event = DataGetter.get_event(event_id)
        if not event.has_session_speakers:
            abort(404)
        DataManager.add_session_to_event(request, event_id)
        if login.current_user.is_authenticated:
            flash("Your session proposal has been submitted", "success")
            return redirect(url_for('my_sessions.display_my_sessions_view', event_id=event_id))
        else:
            flash(Markup("Your session proposal has been submitted. Please login/register with <strong><u>" + email + "</u></strong> to manage it."), "success")
            return redirect(url_for('admin.login_view', next=url_for('my_sessions.display_my_sessions_view')))

    @expose('/<int:event_id>/coc/', methods=('GET',))
    def display_event_coc(self, event_id):
        event = get_published_event_or_abort(event_id)
        placeholder_images = DataGetter.get_event_default_images()
        accepted_sessions = DataGetter.get_sessions(event_id)
        call_for_speakers = DataGetter.get_call_for_papers(event_id).first()
        if not (event.code_of_conduct and event.code_of_conduct != '' and event.code_of_conduct != ' '):
            abort(404)
        return self.render('/gentelella/guest/event/code_of_conduct.html', event=event,
                           placeholder_images=placeholder_images,
                           accepted_sessions=accepted_sessions,
                           call_for_speakers=call_for_speakers)

    # SLUGGED PATHS

    @expose('/<int:event_id>/<slug>/')
    def display_event_detail_home_slugged(self, event_id, slug):
        return self.display_event_detail_home(event_id)

    @expose('/<int:event_id>/<slug>/sessions/')
    def display_event_sessions_slugged(self, event_id, slug):
        return self.display_event_sessions(event_id)
