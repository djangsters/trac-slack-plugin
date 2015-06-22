import json
import requests
from trac.core import Component, implements
from trac.config import Option
from trac.ticket.api import ITicketChangeListener


def prepare_ticket_values(ticket, action=None):
    values = ticket.values.copy()
    values['id'] = "#" + str(ticket.id)
    values['action'] = action
    values['url'] = ticket.env.abs_href.ticket(ticket.id)
    values['project'] = ticket.env.project_name.encode('utf-8').strip()
    values['attrib'] = ''
    values['changes'] = ''
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

    def notify(self, type, values):
        # values['author'] = re.sub(r' <.*', '', values['author'])
        template = '%(type)s <%(url)s|%(id)s>: %(summary)s [%(action)s by *%(author)s*]'

        if values['action'] == 'closed':
            template += ' :white_check_mark:'

        if values['action'] == 'created':
            template += ' :pushpin:'

        if values['attrib']:
            template += '\n```%(attrib)s```'

        if values.get('changes', False):
            template += '\n```%(changes)s```'

        if values['description']:
            template += ' \n```%(description)s```'

        if values['comment']:
            template += '\n>>>%(comment)s'

        message = template % values
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

        data = {"text": message.encode('utf-8').strip()}
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
        values = prepare_ticket_values(ticket, 'created')
        values['author'] = values['reporter']
        values['comment'] = ''
        fields = self.fields.split(',')
        attrib = []

        for field in fields:
            if ticket[field] != '':
                attrib.append('  * %s: %s' % (field, ticket[field]))

        values['attrib'] = "\n".join(attrib) or ''

        self.notify('ticket', values)

    def ticket_changed(self, ticket, comment, author, old_values):
        action = 'changed'
        if 'status' in old_values:
            if 'status' in ticket.values:
                if ticket.values['status'] != old_values['status']:
                    action = ticket.values['status']
        values = prepare_ticket_values(ticket, action)
        values.update({
            'comment': comment or '',
            'author': author or '',
            'old_values': old_values
        })

        if 'description' not in old_values.keys():
            values['description'] = ''

        fields = self.fields.split(',')
        changes = []

        for field in fields:
            if field in old_values.keys():
                changes.append('  * %s: %s => %s' %
                               (field, old_values[field], ticket[field]))

        values['changes'] = "\n".join(changes)

        self.notify('ticket', values)

    def ticket_deleted(self, ticket):
        pass
