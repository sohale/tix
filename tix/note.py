import os
import re
import utils
import collections
from control import UserMode

TODO_REGEX = r'\b(TODO|DEADLINE)\b'
NOT_TODO_REGEX = r'\b(NOTODO|NODEADLINE)\b'

class Note(object):
  """The structure used to store all information for each note file."""
  def __init__(self, filename, path, text):
    self.is_shown = False
    self.text = text

    self.filename = filename
    self.path = path

    self.id = None
    self.is_todo = False
    self.first_line = ""

    #self.modes = set()
    self.modes = utils.get_all_tags(self.text)
    #self.modes = filter(lambda m: m != "#notodo", self.modes)
    self.is_processed = False

  def fullpath(self):
    return os.path.join(self.path, self.filename)

  def is_a_match(self, regex, flags = 0):
    try:
      if regex.strip() is '': return True
      regex = regex.replace('#', '\\#')
      return re.search(regex, self.text,
          re.MULTILINE | re.DOTALL | re.VERBOSE | flags)
    except re.error:
      return True

  def process_meta(self, id):
    self.id = id
    self.is_todo = self.is_a_match(TODO_REGEX) and not self.is_a_match(NOT_TODO_REGEX)
    self.is_someday = self.is_a_match(r'\b(SOMEDAY)\b')
    self.first_line = utils.get_first_line(self.text)
    self.is_processed = True
    self.text = " ".join(set([w.lower() for w in self.text.replace(r'\n',' ').split(' ')])) # self.text[:200] # FIXME
    #self.nbr_of_lines = utils.get_number_of_lines(self.text, 80)

  def is_search_match(self, regex):
    return self.is_a_match(regex, re.IGNORECASE)

  def visible(self, visibility):
    self.is_shown = visibility

  def load_fulltext_from_file(self):
    with open(self.fullpath(), 'r') as f:
      return unicode(f.read())

  def write_text_to_file(self, new_text):
    if not new_text: return
    with open(self.fullpath(), 'w') as f:
      f.write(new_text)

  def archive_note(self):
    # TODO, if decided.
    raise NotImplemented

  def edit(self):
    fullpath = self.fullpath() # os.path.join(self.path, self.filename)

    utils.open_file_in_editor(fullpath)
    with open(fullpath, 'r') as f:
      note_content = f.read()
      return Note(self.filename, self.path, note_content)
    return None

class NoteList(collections.MutableSequence):
  """Holds all loaded notes."""
  def __init__(self):
    self.list = list()
    self.oktype = Note
    self._modes_set = set([UserMode.ALL, UserMode.NOTAG])

  def load(self, root_dir, recursive, function_while_processing=None): # FIXME root dir? meh.
    from control import Control

    if not os.path.exists(root_dir) or not os.path.isdir(root_dir):
      return

    self.reset()

    # look at current dir if config's path is empty:
    if not utils.user_configurations['NOTEPATH']:
      utils.user_configurations['NOTEPATH'].add(root_dir)

    if recursive:
      for dir_path in utils.user_configurations['NOTEPATH']:
        if not os.path.exists(dir_path):
          continue
        for file_path, dirs, files in os.walk(dir_path):
          if '.git' in file_path.split(os.sep):
            continue
          self.extend(self.read_notes(file_path, files))
          continue
    else:
      for file_path in utils.user_configurations['NOTEPATH']:
        if not os.path.exists(file_path):
          continue
        files = os.listdir(file_path)
        self.extend(self.read_notes(file_path, files))

    self.sort_by_modification_date()
    
    self.filter(function_while_processing)

    #list_modes = self.modes()
    #current_mode = list_modes[UserMode.current]
    #for i, note in enumerate(self.list):
    #  note.process_meta(i)
    #  if (current_mode == UserMode.ALL or current_mode in note.modes) \
    #  and note.is_search_match(Control.get_last_regex()):
    #    note.visible(True)
    #  else:
    #    note.visible(False)
    #  if function_while_processing and i % 100 == 0:
    #    function_while_processing()

  def filter(self, function_while_processing=None):
    from control import Control
    list_modes = self.modes()
    current_mode = list_modes[UserMode.current]
    for i, note in enumerate(self.list):
      if not note.is_processed: note.process_meta(i)
      if (current_mode == UserMode.ALL or current_mode in note.modes) \
      and note.is_search_match(Control.get_last_regex()):
        note.visible(True)
      else:
        note.visible(False)
      if function_while_processing and i % 100 == 0:
        function_while_processing()

  def read_notes(self, path, filenames, firstline_only=False):
    notes = NoteList()
    for filename in filenames:
      if not re.search(utils.FILENAME_WHITELIST_REGEX, filename):
        continue
      full_path = os.path.join(path, filename)
      if os.path.isfile(full_path):
        with open(full_path, 'r') as f:
          if firstline_only:
            text = f.readline()
          else:
            text = f.read()
          #if not utils.is_binary(text):
          notes.append(Note(filename, path, text))
    return notes

  def reset(self):
    del self.list[:]

  def check(self, v):
    if not isinstance(v, self.oktype):
      raise TypeError, v

  def group_todo(self):
    todo_list = [n for n in self.list if n.is_todo]
    self.list = [n for n in self.list if not n.is_todo]
    self.list = todo_list + self.list

  def sort_by_modification_date(self):
    self.list = sorted(self.list,
        key=lambda note: utils.get_modification_date(note.fullpath()),
        reverse=True)

  def sort_by_filename(self):
    self.list = sorted(self.list,
        key=lambda note: note.fullpath(),
        reverse=True)

  def has_note(self):
    return self.list != []

  def __setitem__(self, i, v):
    self.check(v)
    self.list[i] = v

  def extend(self, values):
    if not isinstance(values, NoteList):
      raise TypeError, values

    for v in values:
      self.list.append(v)
      self._modes_set = self._modes_set.union(v.modes)

  def insert(self, i, v):
    self.check(v)
    self._modes_set = self._modes_set.union(v.modes)
    self.list.insert(i, v)

  def modes(self):
    def comp(a, b):
      v1 = re.sub(utils.TAG_STARTS_WITH, 'z', a.lower(), 1)
      v2 = re.sub(utils.TAG_STARTS_WITH, 'z', b.lower(), 1)
      return cmp(v1, v2)
    return sorted(list(self._modes_set), cmp=comp)

  def get_visible(self, key):
    index = 0
    for i in self.list:
      if i.is_shown:
        if index == key:
          return i
        index += 1
    return self.list[key]

  def __len__(self):
    #- list of shown items
    return len(filter(lambda n: n.is_shown, self.list))

  def __getitem__(self, key):
    return self.list[key]

  def __delitem__(self, i): del self.list[i]
  def __str__(self): return str(self.list)
