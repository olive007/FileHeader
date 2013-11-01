#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: lime
# @Date:   2013-10-28 13:39:48
# @Email:  shiyanhui66@gmail.com
# @Last modified by:   lime
# @Last Modified time: 2013-11-01 11:15:20

import os
import sys
import re
import sublime
import sublime_plugin
import functools
import threading
import zipfile
import getpass

from datetime import datetime

INSTALLED_PLGIN_PATH = os.path.abspath(os.path.dirname(__file__))

PLUGIN_NAME = 'FileHeader'
PACKAGES_PATH = sublime.packages_path()
PLUGIN_PATH = os.path.join(PACKAGES_PATH, PLUGIN_NAME)
TEMPLATE_PATH = os.path.join(PLUGIN_PATH, 'template')

sys.path.insert(0, PLUGIN_PATH)

def plugin_loaded():
    '''ST3'''

    if not os.path.exists(PLUGIN_PATH):
        os.mkdir(PLUGIN_PATH)

        if os.path.exists(INSTALLED_PLGIN_PATH):
            z = zipfile.ZipFile(INSTALLED_PLGIN_PATH, 'r')
            for f in z.namelist():
                z.extract(f, PLUGIN_PATH)
            z.close()

def Window():
    '''Get current act``ive window'''

    return sublime.active_window()

def Settings():
    '''Get settings'''

    return sublime.load_settings('%s.sublime-settings' % PLUGIN_NAME)

def get_template(syntax_type):
    '''Get template correspond `syntax_type`'''

    tmpl_name = '%s.tmpl' % syntax_type
    tmpl_file = os.path.join(TEMPLATE_PATH, tmpl_name)

    options = Settings().get('options')
    custom_template_path = options['custom_template_path']
    if custom_template_path:
        _ = os.path.join(custom_template_path, tmpl_name)
        if os.path.exists(_) and os.path.isfile(_):
            tmpl_file = _

    try:
        template_file = open(tmpl_file, 'r')
        contents = template_file.read() + '\n'
        template_file.close()
    except Exception as e:
        sublime.error_message(str(e))
        contents = ''
    return contents

def get_strftime():
    '''Get `time_format` setting'''

    options = Settings().get('options')
    _ = ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%H:%M:%S']
    try:
        format = _[options['time_format']]
    except IndexError:
        format = _[0]
    return format

def get_user():
    '''Get user'''

    if sys.version < '3':
        import commands as process
    else:    
        import subprocess as process
          
    user = getpass.getuser()
    status, _ = process.getstatusoutput('git status')
    if status == 0:
        status, output = process.getstatusoutput('git config --get user.name')
        if status == 0 and output:
            user = output

    return user

def get_args(syntax_type):
    '''Get the args rendered'''

    options = Settings().get('options')
    args = Settings().get('Default')
    args.update(Settings().get(syntax_type, {}))

    format = get_strftime()
    time = datetime.now().strftime(format)

    args.update({'create_time': time})
    args.update({'last_modified_time': time})

    user = get_user()

    if 'author' not in args:
        args.update({'author': user})

    if 'last_modified_by' not in args:
        args.update({'last_modified_by': user})

    return args

def render_template(syntax_type):
    '''Render the template correspond `syntax_type`'''

    from jinja2 import Template
    try:
        template = Template(get_template(syntax_type))
        render_string = template.render(get_args(syntax_type))
    except Exception as e:
        sublime.error_message(str(e))
        render_string = ''
    return render_string

def get_syntax_type(name):
    '''Judge `syntax_type` according to to `name`'''
    options = Settings().get('options')
    syntax_type = options['syntax_when_not_match']
    file_suffix_mapping = options['file_suffix_mapping']

    name = name.split('.')
    if len(name) <= 1:
        return syntax_type

    try:
        syntax_type = file_suffix_mapping[name[-1]]
    except KeyError:
        pass

    return syntax_type

def get_syntax_file(syntax_type):
    '''Get syntax file path'''

    lang2tmL = {
        'Graphviz': 'DOT',
        'RestructuredText': 'reStructuredText',
        'ShellScript': 'Shell-Unix-Generic',
        'TCL': 'Tcl',
        'Text': 'Plain text',
    }

    tmL = lang2tmL.get(syntax_type, syntax_type)
    return 'Packages/%s/%s.tmLanguage' % (syntax_type, tmL)

def block(view, callback, *args, **kwargs):
    '''Ensure the callback is executed'''

    def _block():
        if view.is_loading():
            sublime.set_timeout(_block, 100)
        else:
            callback(*args, **kwargs)

    _block()


class FileHeaderNewFileCommand(sublime_plugin.WindowCommand):
    '''Create a new file with header'''

    def new_file(self, path, syntax_type):
        if os.path.exists(path):
            sublime.error_message('File exists!')
            return

        header = render_template(syntax_type)

        try:
            with open(path, 'w+') as f:
                f.write(header)
                f.close()
        except Exception as e:
            sublime.error_message(str(e))
            return

        new_file = Window().open_file(path)
        block(new_file, new_file.set_syntax_file, get_syntax_file(syntax_type))
        block(new_file, new_file.show_at_center, 0)

    def new_view(self, syntax_type, name):
        header = render_template(syntax_type)
        new_file = Window().new_file()
        new_file.set_name(name)
        new_file.run_command('insert', {'characters': header})
        new_file.set_syntax_file(get_syntax_file(syntax_type))

    def get_path(self, paths):
        path = None
        if not paths:
            current_view = Window().active_view()
            if current_view:
                file_name = current_view.file_name()
                if file_name is not None:
                    path = os.path.dirname(file_name)
        else:
            path = paths[0]
            if not os.path.isdir(path):
                path = os.path.dirname(path)

        if path is not None:
            path = os.path.abspath(path)

        return path

    def on_done(self, path, name):
        if not name:
            return 

        syntax_type = get_syntax_type(name)
                
        if path is None:
            self.new_view(syntax_type, name)
        else:
            path = os.path.join(path, name)
            self.new_file(path, syntax_type)

    def run(self, paths=[]):
        path = self.get_path(paths)

        caption = 'File Name:'
        # if caption is not None:
        #     caption = 'File Nanme: (Saved in %s)' % path

        Window().run_command('hide_panel')
        Window().show_input_panel(caption, '', functools.partial(
                                  self.on_done, path), None, None)


class BackgroundAddHeaderThread(threading.Thread):
    '''Add header in background.'''

    def __init__(self, path):
        self.path = path
        super(BackgroundAddHeaderThread, self).__init__()

    def run(self):
            
        syntax_type = get_syntax_type(self.path)
        header = render_template(syntax_type)

        try:
            with open(self.path, 'r') as f:
                contents = header + f.read()
                f.close()

            with open(self.path, 'w') as f:
                f.write(contents)
                f.close()
        except Exception as e:
            sublime.error_message(str(e))


class AddFileHeaderCommand(sublime_plugin.TextCommand):
    '''Command: add `header` in a file'''

    def run(self, edit, path):
        syntax_type = get_syntax_type(path)
        header = render_template(syntax_type)
        self.view.insert(edit, 0, header)

class FileHeaderAddHeaderCommand(sublime_plugin.WindowCommand):
    '''Conmmand: add `header` in a file or directory'''

    def add(self, path):
        '''Add to a file'''

        options = Settings().get('options')
        whether_open_file = options['open_file_when_add_header_to_directory'] 

        if whether_open_file:
            modified_file = Window().open_file(path)
            block(modified_file, modified_file.run_command, 
                  'add_file_header', {'path': path})
            block(modified_file, modified_file.show_at_center, 0)
        else:
            thread = BackgroundAddHeaderThread(path)
            thread.start()

    def walk(self, path):
        '''Add files in the path'''
        
        for root, subdirs, files in os.walk(path):
            for f in files:
                file_name = os.path.join(root, f)
                self.add(file_name)
                
    def on_done(self, path):
        if not path:
            return

        if not os.path.exists(path):
            sublime.error_message('Path not exists!')
            return

        path = os.path.abspath(path)

        if os.path.isfile(path):
            self.add(path)
        elif os.path.isdir(path):
            self.walk(path)

    def run(self, paths=[]):
        initial_text = ''
        if paths:
            initial_text = os.path.abspath(paths[0])
        else:
            try:
                initial_text = Window().active_view().file_name()
            except:
                pass

        options = Settings().get('options')
        show_input_panel_when_add_header = (options[
            'show_input_panel_when_add_header'])

        if not show_input_panel_when_add_header:
            self.on_done(initial_text)
            return

        Window().run_command('hide_panel')
        Window().show_input_panel('Modified File or Directory:', initial_text, 
                                  self.on_done, None, None)


class FileHeaderReplaceCommand(sublime_plugin.TextCommand):
    '''Replace contents in the `region` with `stirng`'''

    def run(self, edit, a, b, strings):
        region = sublime.Region(int(a), int(b))
        self.view.replace(edit, region, strings)


class UpdateModifiedTimeListener(sublime_plugin.EventListener):
    '''Auto update `last_modified_time` when save file'''

    MODIFIED_TIME_REGEX = re.compile('\{\{\s*last_modified_time\s*\}\}') 
    MODIFIED_BY_REGEX = re.compile('\{\{\s*last_modified_by\s*\}\}')

    def time_pattern(self):
        options = Settings().get('options')

        choice = options['time_format']
        _ = [0, 1, 2]
        if choice not in _:
            choice = 0

        _ = ['\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}', 
             '\d{4}-\d{2}-\d{2}', '\d{2}:\d{2}:\d{2}']
        return _[choice]

    def update_last_modified(self, view, what):
        what = what.upper()
        syntax_type = get_syntax_type(view.file_name())
        template = get_template(syntax_type)    
        lines = template.split('\n')

        line_pattern = None
        for line in lines:
            regex = getattr(UpdateModifiedTimeListener, 'MODIFIED_%s_REGEX' %
                            what)
            search = regex.search(line)

            if search is not None:
                var = search.group()
                index = line.find(var)

                for i in range(index - 1, 0, -1):
                    if line[i] != ' ':
                        space_start = i + 1
                        line_header = line[: space_start]
                        break        

                if what == 'BY':
                    line_pattern = '%s.*\n' % line_header
                else:
                    line_pattern = '%s\s*%s.*\n' % (line_header, 
                                                    self.time_pattern())
                break

        if line_pattern is not None:
            _ = view.find(line_pattern, 0)
            if(_ != sublime.Region(-1, -1) and _ is not None):
                a = _.a + space_start
                b = _.b - 1    

                spaces = (index - space_start) * ' '
                if what == 'BY':
                    args = get_args(syntax_type)
                    strings = (spaces+ args['last_modified_by'])
                else:                    
                    strftime = get_strftime()
                    time = datetime.now().strftime(strftime)
                    strings = (spaces + time)
                
                view.run_command('file_header_replace', 
                                 {'a': a, 'b': b,'strings': strings})

    def on_pre_save(self, view):

        self.update_last_modified(view, 'by')
        self.update_last_modified(view, 'time')