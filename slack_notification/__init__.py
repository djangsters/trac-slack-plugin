# -*- coding: utf8 -*-

import json
import requests
from trac.core import Component, implements
from trac.config import Option
from trac.ticket.api import ITicketChangeListener


def prepare_ticket_values(ticket):
    values = ticket.values.copy()
    values['id'] = "#" + str(ticket.id)
    values['url'] = ticket.env.abs_href.ticket(ticket.id)
    values['project'] = ticket.env.project_name.encode('utf-8').strip()
    return values


class SlackNotifcationPlugin(Component):
    implements(ITicketChangeListener)
    webhook = Option('slack', 'webhook', 'https://hooks.slack.com/services/',
                     doc="Incoming webhook for slack")
    channel = Option('slack', 'channel', '',
                     doc="Channel name on slack")
    username = Option('slack', 'username', '',
                      doc="Username of the bot on slack notify")
    fields = Option('slack', 'fields', 'type,component,resolution',
                    doc="Fields that should be reported")

    def notify(self, action, values):
        # values['author'] = re.sub(r' <.*', '', values['author'])
        values["author"] = values["author"].title()
        values["type"] = values["type"].title()

        text = ""
        add_author = ('comment' not in values)
        if action == "new":
            text = "New "
            add_author = True

        text += u"{type} <{url}|{id}>: {summary}".format(**values)

        if "new_status" in values:
            text += u" *⇒ {}*".format(values["new_status"])
            add_author = True

        if add_author:
            text += u" _by_ *{}*".format(values['author'])

        fields = []

        for k, v in values.get('attrib', {}).items():
            fields.append({
                "title": k.title(),
                "value": v,
                "short": True,
            })

        for k, v in values.get('changes', {}).items():
            fields.append({
                "title": k.title(),
                "value": u"{} ⇒ {}".format(v[0], v[1]) if v[0] else v[1],
                "short": True,
            })

        if "description" in values:
            fields.append({
                "title": "Description",
                "value": values['description'],
                "short": False,
            })

        if "comment" in values:
            field_title = u"Comment"
            if not add_author:
                field_title += u" by {}".format(values["author"])
            fields.append({
                "title": field_title,
                "value": values['comment'],
                "short": False,
            })

        # message += "\n\n"
        # message += '\n'.join(['%s:%s' % (key, value) for (key, value) in values.items()])

        channel = self.channel
        if ":" in channel:
            channels = channel.split(",")
            channel = ''
            for entry in channels:
                client, chan = entry.split(":", 1)
                if values.get('client').lower() == client.strip().lower():
                    channel = chan.strip()
                    break

        data = {"attachments": [{
            "fallback": text.strip(),
            "pretext": text.strip(),
            "color": "#EEEEEE",
            "mrkdwn_in": ["pretext"],
            "fields": fields
        }]}
        if channel:
            data["channel"] = channel
        if self.username:
            data["username"] = self.username

        try:
            requests.post(self.webhook, data={"payload": json.dumps(data)})
        except requests.exceptions.RequestException:
            return False
        return True

    def ticket_created(self, ticket):
        values = prepare_ticket_values(ticket)
        values['author'] = values['reporter']
        fields = self.fields.split(',')
        attrib = {}

        for field in fields:
            if ticket[field] != '':
                attrib[field] = ticket[field]

        values['attrib'] = attrib

        self.notify('new', values)

    def ticket_changed(self, ticket, comment, author, old_values):
        values = prepare_ticket_values(ticket)
        if comment:
            values['comment'] = comment
        values['author'] = author or 'unknown'
        if 'status' in old_values:
            if ticket.values.get('status') != old_values['status']:
                values["new_status"] = ticket.values['status']

        if 'description' not in old_values.keys():
            del values['description']

        fields = self.fields.split(',')
        changes = {}

        for field in fields:
            if field in old_values.keys():
                changes[field] = (old_values[field], ticket[field])

        values['changes'] = changes

        self.notify('edit', values)

    def ticket_deleted(self, ticket):
        pass
