from jinja2 import Markup, escape



def link(element, href, new_tab=False):
    return '<a href="{}" {}>{}</a>'.format(href, 'target="_blank"' if new_tab else "", element)



def style(element, classes):
    return '<span class="{}">{}</span>'.format(classes, element)



def summary(element, details):
    return '<details><summary>{}</summary>{}</details>'.format(element, details)



def formfield(field):
    returnn field(class="form-control")
