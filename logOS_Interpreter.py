#!usr/bin/python3.8
from lark import Lark, Transformer
from functools import wraps
from dataclasses import dataclass
import time, secrets, pathlib, urllib.request
from decimal import Decimal, Context, localcontext, MAX_PREC, MAX_EMAX, MIN_EMIN, FloatOperation

grammar = r"""
program: line* command? //a program is one or more lines
line: command_line | blank_line
blank_line: newline //nothing, followed by a newline
command_line: command newline
command: command_name space command_args //a command, plus args
    | command_name //no args; just command
command_name: /\S+/  //One or more non-whitespace characters
command_args: /[^\n\r]+/  //one or more characters that aren't line feeds or carriage returns
space: / /+  //one or more spaces
newline: NEWLINE
%import common.NEWLINE
"""

class TreeParser(Transformer):
    '''Turns a tree into an ordered list of commands
    where each command is a tuple of
    (command_name, command_args), both strings'''
    def program(self, items):
        #None represents blank lines, which are filtered out
        return [item for item in items if item is not None]
    def line(self, items):
        (items,) = items
        return items
    def command(self, items):
        command_name, *rest = items
        command_args = ""
        if len(rest) == 2:
            _, command_args = rest
        return command_name, command_args
    def command_line(self, items):
        return items[0]
    def command_name(self, items):
        (item,) = items
        return str(item)
    def command_args(self, items):
        (item,) = items
        return str(item)
    def blank_line(self, items):
        return None

parser = Lark(grammar, start="program", parser="lalr", transformer=TreeParser())

calculation_grammar = r"""
primary_expression: secondary_expression (addition | subtraction)*
!addition: "+" secondary_expression
!subtraction: "-" secondary_expression
secondary_expression: tertiary_expression (multiplication | division)*
!multiplication: "*" tertiary_expression
!division: "/" tertiary_expression
tertiary_expression: quaternary_expression exponentiation*
!exponentiation: "^" quaternary_expression
quaternary_expression: number | bracketed_expression
bracketed_expression: "(" primary_expression ")"
number: SIGNED_NUMBER
%import common.SIGNED_NUMBER
%import common.WS
%ignore WS //ignore whitespace
"""

class CalculationTreeParser(Transformer):
    '''Calculates from a Lark parse tree of a arithmetic expression'''
    operations_funcs = {
        "*":lambda x, y: x * y,
        "/":lambda x, y: x / y,
        "+":lambda x, y: x + y,
        "-":lambda x, y: x - y,
        "^":lambda x, y: x ** y,}
    def unpack(args):
        (inner_value,) = args
        return inner_value
    def operate(args):
        accumulator, *operations = args
        for op_type, op_arg in operations:
            op_func = CalculationTreeParser.operations_funcs[op_type]
            accumulator = op_func(accumulator, op_arg)
        return accumulator
    def to_operation(args):
        op, value = args
        return op.value, value
    def number(args):
        (number_string,) = args
        return Decimal(number_string)
    bracketed_expression = unpack
    quaternary_expression = operate
    tertiary_expression = operate
    secondary_expression = operate
    primary_expression = operate
    multiplication = division = addition = subtraction = exponentiation = to_operation

calculation_parser = Lark(
    calculation_grammar,
    start="primary_expression",
    parser="lalr",
    transformer=CalculationTreeParser)

class Interpreter:
    def __init__(self, code, **kwargs):
        if isinstance(code, str):
            code = parse_logos(code)
        if "log_state" not in kwargs:
            kwargs["log_state"] = self.log_state
        self.source = code
        self.remaining_code = self.source
        self.runtime = Runtime(**kwargs)
        self.history = []
        self.repl_history = []
        next(self.runtime)
    def run_once(self, command_and_args=None):
        if command_and_args is None:
            (command, args), *self.remaining_code = self.remaining_code
        else:
            (command, args) = command_and_args
        self.history.append((command, args))
        if (remaining_code_changes := self.runtime.send((command, args))) is not None:
            self.remaining_code = remaining_code_changes(self.remaining_code)
        return
    def run_all(self):
        while self.remaining_code:
            self.run_once()
    def repl_once(self):
        self.run_all()
        next_command = parse_logos(input(">>>> "))[0]
        self.repl_history.append(next_command)
        self.run_once(next_command)
        state = self.most_recent_state
        buffer = state.current_buffer
        program_name = state.current_program_name
        clipboard = state.clipboard
        print(f"Clipboard: {clipboard}")
        print(f"Buffer of {program_name}: {buffer}")
    def repl(self):
        while True:
            self.repl_once()
    def log_state(self, state):
        self.most_recent_state = state

def functional_command(func):
    @wraps(func)
    def inner(args, state):
        old_buffer = state.current_buffer
        new_buffer = func(args, old_buffer)
        state.current_buffer = new_buffer
        return None, state
    return inner

class BaseProgram:
    '''Base class for program types'''
    def __init__(self, initial_buffer="", *args, **kwargs):
        '''All programs have a buffer of text that their commands operate on'''
        self.buffer = initial_buffer
    def __repr__(self):
        buffer = self.buffer
        if len(buffer) > 25:
            buffer = buffer[:20] + "..."
        return f"<Program: {self.name()} {buffer=}>"
    @classmethod
    def name(cls):
        '''Program name, calculated from a program's class name'''
        return cls.__name__

class LimitedCommandProgram(BaseProgram):
    '''Base class for programs that can't accept all arguments, only a limited set'''
    def get_command(self, command_name):
        return self._commands[command_name]

class Desktop(BaseProgram):
    '''Default program used for loading other programs'''
    def get_command(self, command_name):
        '''Any command is handled by trying to load that program'''
        def program_opener(args, state):
            if command_name in state.open_programs:
                raise ValueError(f"{command_name} already started!")
            elif command_name in state.library:
                #for starting a program with buffer already initialised:
                buffer = args
                #create a new program instance
                new_program = state.library[command_name](buffer)
                #append new program to collection of running programs
            else:
                buffer = args
                #create an inert note program
                new_program = create_note_program(command_name, args)(buffer)
            state.open_programs[command_name] = new_program
            #switch to chosen program
            state.current_program_name = command_name
            return None, state
        return program_opener

def create_note_program(name, buffer):
    def altered_init(self, *args, **kwargs):
        BaseProgram.__init__(self, *args, **kwargs)
        print(f'making Note with {buffer=}')
        self.buffer = buffer
    def command_getter(self, command_name):
        error_message = f"Trying to run command {command_name} on note program {name}"
        raise RuntimeError(error_message)
    class_dict = {"__init__":altered_init, "get_command":command_getter}
    return type(name, (BaseProgram,), class_dict)

class Email(LimitedCommandProgram):
    '''IO program, themed around an email client'''
    @functional_command
    def _send(args, buffer):
        '''Output from buffer'''
        assert not args
        print(buffer)
        return buffer
    @functional_command
    def _refresh(args, buffer):
        '''Input to buffer'''
        assert not args
        return input("Program requests input: ")
    _commands = {"send":_send, "refresh":_refresh}

class Editor(LimitedCommandProgram):
    '''Text editor, themed around Notepad or WordPad'''
    #units dict gives separator for the unit e.g. lines separated by \n
    units = {"characters":("",), "words":(" ","\n"), "lines":("\n",)}
    quotemarks = {"quotemark", "a quotemark", "Otto von Quotemark"}
    newlines = {"newline", "a newline"}
    @classmethod
    def unit_split(cls, string, delimiters):
        if len(delimiters) == 0:
            return [string]
        if "" in delimiters:
            return list(string)
        *other_delimiters, last_delimiter = delimiters
        split_by_others = cls.unit_split(string, other_delimiters)
        nested_splits = [
            subsplit.split(last_delimiter)
            for subsplit
            in split_by_others]
        flattened_splits = [
            inner_part
            for top_level_part in nested_splits
            for inner_part in top_level_part]
        return flattened_splits
    @classmethod
    def extract_replacement(cls, string):
        string = string.strip()
        if string in cls.quotemarks:
            return '"'
        if string in cls.newlines:
            return "\n"
        if len(string) < 2:
            return None
        if string.startswith('"') and string.endswith('"'):
            return string[1:-1]
        return None
    @functional_command
    def _write(args, buffer):
        '''Append args to buffer (to end of buffer)'''
        args = args.strip()
        if args in {"", "newline", "a newline"}:
            buffer += "\n"
            return buffer
        if args in {'"', "quotemark", "a quotemark"}:
            buffer += '"'
            return buffer
        assert args.startswith('"') and args.endswith('"')
        buffer += args[1:-1]
        return buffer
    @functional_command
    def _backspace(args, buffer):
        '''Remove some number of units, default one character, from end of buffer
        Takes form `backspace <number_to_backspace=1> <unit=characters>`'''
        #logic to parse arguments backspace:
        split_args = args.split(" ")
        units = Editor.units
        if all(split_arg == "" for split_arg in split_args):
            number_to_backspace = 1
            unit = units["characters"]
        elif len(split_args) == 1:
            if (string_arg := split_args[0]) in units:
                number_to_backspace = 1
                unit = units[string_arg]
            else:
                unit = units["characters"]
                number_to_backspace = int(string_arg)
        else:
            number_string, unit_string = split_args
            unit = units[unit_string]
            number_to_backspace = int(number_string)
        #do the backspacing
        for _ in range(number_to_backspace):
            while buffer and not any(
                buffer.endswith(unit_component)
                for unit_component
                in unit):
                    #backspace characters until we get to a unit specifier
                    buffer = buffer[:-1]
            buffer = buffer[:-1] #backspace the unit specifier
        return buffer
    @functional_command
    def _replace(args, buffer):
        sep = " with "
        extract = Editor.extract_replacement
        #try parse from front:
        first, *rest = args.split(sep)
        #iterate through every interpretation of symbols
        while (extract(first) is None
               or extract(sep.join(rest)) is None):
            if not rest:
                msg = args + " can't be parsed as replacement"
                raise ValueError(msg)
            second_first, *rest = rest
            first += sep + second_first
        last = sep.join(rest)
        a = extract(first)
        b = extract(last)
        buffer = buffer.replace(a, b)
        return buffer
    @functional_command
    def _count(args, buffer):
        units = Editor.units
        if args == "":
            args = "characters"
        if args in units:
            if buffer == "":
                return "0"
            split_buffer = Editor.unit_split(buffer, units[args])
            return str(len(tuple(split for split in split_buffer if split != "")))
        else:
            args = args.strip()
            assert args.startswith('"') and args.endswith('"')
            return str(buffer.count(args.strip('"')))
        return buffer
    def _append(args, state):
        assert args in ["the clipboard", "from clipboard"]
        state.current_buffer += state.clipboard
        state.clipboard = ""
        return None, state
    @functional_command
    def _tailor(args, buffer):
        """
        Replace buffer with some number of units from end of buffer.
        See _backspace for more info.
        """
        #logic to parse arguments for selection:
        split_args = args.split(" ")
        units = Editor.units
        if all(split_arg == "" for split_arg in split_args):
            number_to_select = 1
            unit = units["characters"]
        elif len(split_args) == 1:
            if (string_arg := split_args[0]) in units:
                number_to_select = 1
                unit = units[string_arg]
            else:
                unit = units["characters"]
                number_to_select = int(string_arg)
        else:
            number_string, unit_string = split_args
            unit = units[unit_string]
            number_to_select = int(number_string)
        #replace buffer:
        selection = selection_plus_spec = ""
        for _ in range(number_to_select):
            print(f"{selection=} {selection_plus_spec=}")
            selection = selection_plus_spec
            while buffer and not any(
                "".join(buffer).endswith(unit_component)
                for unit_component
                in unit):
                    #pop characters,
                    #until we get to a unit specifier
                    *buffer, last_char = buffer
                    selection = last_char + selection
            selection_plus_spec = selection
            print(selection)
            while buffer and any(
                "".join(buffer).endswith(unit_component)
                for unit_component
                in unit):
                #extract the unit specifier
                *buffer, last_char = buffer
                selection_plus_spec = last_char + selection
        buffer = selection
        print(selection, selection_plus_spec)
        return buffer
    _commands = {
        "write":_write,
        "backspace":_backspace,
        "replace":_replace,
        "count":_count,
        "append":_append,
        "tailor":_tailor}

class Calculator(LimitedCommandProgram):
    '''Arithmetic processing program'''
    def _calculate(string):
        '''evaluate expression'''
        #configure settings for Decimal module
        calculator_context = Context(
            prec=MAX_PREC,
            Emax=MAX_EMAX,
            Emin=MIN_EMIN,
            capitals=0,
            clamp=0,
            traps=[FloatOperation])
        with localcontext(calculator_context):
            decimal_answer = calculation_parser.parse(string)
        new_string = str(float(decimal_answer)).rstrip("0").rstrip(".")
        return new_string
    @functional_command
    def _equals(args, buffer):
        assert args == ""
        buffer = Calculator._calculate(buffer)
        return buffer
    def _append_and_equals(operator):
        @functional_command
        def command(args, buffer):
            buffer = Calculator._calculate(buffer + operator + args)
            return buffer
        return command
    _commands = {"=":_equals}
    for op in "*/+-^": #can't use dict comprehension because of Python scoping bug :/
        _commands[op] = _append_and_equals(op)

class Terminal(LimitedCommandProgram):
    '''Used for flow control (along with 'execute' keyword)'''
    def _run(args, state):
        '''Replace running commands with buffer
        i.e. stop executing whatever was previously running,
        and instead run the buffer'''
        assert args == ""
        new_instructions = parse_logos(state.current_buffer)
        def replacer(old_instructions):
            return new_instructions
        state.clear_buffer()
        return replacer, state
    _commands = {"run":_run}

class Files(LimitedCommandProgram):
    '''Used for interfacing with the real filesystem'''
    @functional_command
    def _create(args, buffer):
        folder_mode_prefix = "the folder at"
        if args.startswith(folder_mode_prefix):
            target_path_str = args.lstrip(folder_mode_prefix).strip()
            folder_not_file = True
        else:
            target_path_str = args.strip()
            folder_not_file = False
        #currently no additional validation wrt Unix format:
        target_path = pathlib.Path(target_path_str)
        target_path = target_path.expanduser().resolve()
        if folder_not_file:
            target_path.mkdir(parents=True)
        else:
            target_path.touch()
        return buffer
    @functional_command
    def _delete(args, buffer):
        folder_mode_prefix = "the folder at"
        if args.startswith(folder_mode_prefix):
            target_path_str = args.lstrip(folder_mode_prefix).strip()
            folder_not_file = True
        else:
            target_path_str = args.strip()
            folder_not_file = False    
        #currently no additional validation wrt Unix format:
        target_path = pathlib.Path(target_path_str)
        target_path = target_path.expanduser().resolve()
        if folder_not_file:
            target_path.rmdir()
        else:
            target_path.unlink()
        return buffer
    @functional_command
    def _load(args, buffer):
        target_path_str = args.strip()
        target_path = pathlib.Path(target_path_str).expanduser().resolve()
        buffer = target_path.read_text(errors="surrogateescape")
        return buffer
    @functional_command
    def _save(args, buffer):
        target_path_str = args.strip()
        target_path = pathlib.Path(target_path_str).expanduser().resolve()
        target_path.write_text(buffer, errors="surrogateescape")
        return ""
    _commands = {"create":_create, "delete":_delete, "load":_save, "save":_save}

class Browser(LimitedCommandProgram):
    @functional_command
    def _navigate(args, buffer):
        arg_prefix = "to "
        assert args.startswith(arg_prefix)
        url = "https://" + args.lstrip(arg_prefix)
        data = buffer.encode() if buffer != "" else None
        request = urllib.request.Request(url, data=data, unverifiable=True)
        with urllib.request.urlopen(request) as response:
            buffer = response.read().decode()
        return buffer
    _commands = {"navigate":_navigate}

class Clock(LimitedCommandProgram):
    units = {
        "secs":"1",
        "seconds":"1",
        "milliseconds":"0.001",
        "mins":"60",
        "minutes":"60"}
    def _prettify_time_struct(struct):
        '''Formatting example:
        8 seconds past 9:06 AM on Monday the 3rd of August, 2019'''
        secs = time.strftime("%-S", struct)
        sec_indicator = "second" if struct.tm_sec == 1 else "seconds"
        time_of_day = time.strftime("%-I:%M %p", struct)
        weekday = time.strftime("%A", struct)
        day = Clock._ordinal_day(struct.tm_mday)
        month_year = time.strftime("%B, %Y", struct)
        return (f"{secs} {sec_indicator} past {time_of_day} "
            f"on {weekday} the {day} of {month_year}")
    def _ordinal_day(day):
        '''Convert an int to a str of it with "st", "nd", "rd" or "th"
        appended appropriately'''
        specific_suffixes = {1: "st", 2: "nd", 3: "rd"}
        if 10 <= day % 100 < 20:
            return f"{day}th"
        if last_digit := day % 10 in specific_suffixes:
            return str(day) + specific_suffixes[last_digit]
        return f"{day}th"
    @functional_command
    def _wait(args, buffer):
        #configure settings for Decimal module
        calculator_context = Context(
            prec=MAX_PREC,
            Emax=MAX_EMAX,
            Emin=MIN_EMIN,
            capitals=0,
            clamp=0,
            traps=[FloatOperation])
        with localcontext(calculator_context):
            for unit in Clock.units:
                if args.rstrip().endswith(unit.rstrip()):
                    ratio = Decimal(Clock.units[unit])
                    args = args.rstrip(unit)
                    break
            else:
                ratio = Decimal(Clock.units["secs"])
            scalar_time_to_wait = Decimal(args.strip())
            time.sleep(float(ratio * scalar_time_to_wait))
        return buffer
    @functional_command
    def _time(args, buffer):
        if args == "in terms of the unix epoch":
            format = "unix"
        elif args == "in terms of utc":
            format = "utc"
        elif args == "in terms of local time":
            format = "local"
        else:
            assert args == ""
            format = "local"
        unix_time = time.time()
        if format == "unix":
            buffer = str(unix_time)
        else:
            if format == "utc":
                time_struct = time.gmtime(unix_time)
            elif format == "local":
                time_struct = time.localtime(unix_time)
            else:
                raise NotImplementedError
            buffer = Clock._prettify_time_struct(time_struct)
        return buffer
    _commands = {"wait":_wait, "time":_time}

class Characters(LimitedCommandProgram):
    @functional_command
    def _unicode(args, buffer):
        integer_codepoints = (int(Decimal(number)) for number in buffer.split())
        buffer = "".join(chr(codepoint) for codepoint in integer_codepoints)
        return buffer
    @functional_command
    def _codepoints(args, buffer):
        buffer = " ".join(str(ord(char)) for char in buffer)
        return buffer
    _commands = {"Unicode":_unicode, "codepoints":_codepoints}

class Mines(LimitedCommandProgram):
    '''Used for generating random bits'''
    @functional_command
    def _generate(args, buffer):
        number_of_bits = int(args)
        if number_of_bits == 0:
            return ""
        bits = secrets.randbits(number_of_bits)
        binary_representation = format(bits, f"0{number_of_bits}b")
        buffer = binary_representation
        return buffer
    _commands = {"generate":_generate}

class Solitaire(LimitedCommandProgram):
    @functional_command
    def _sort(args, buffer):
        raise NotImplementedError
        return buffer
    _commands = {"sort":_sort}

class Assembler(LimitedCommandProgram):
    '''Used for creating program objects from a class'''
    def _compile(args, state):
        program_name, *other_args = args.split()
        assert len(other_args) == 0
        parsed = parse_logos(state.current_buffer)
        name = ""
        commands = {'':[]}
        for command_line in parsed:
            command, parsed_args = command_line
            if command == "name" and parsed_args != "":
                name = parsed_args
            else:
                try:
                    commands[name].append(command_line)
                except KeyError:
                    commands[name] = [command_line]
        
        return None, state
    _commands = {"compile":_compile}

class ProxyProgram(BaseProgram):
    def __init__(self, name, commands, vm_library):
        self.name = lambda: name
        self.interpreter = Interpreter([],
                                       library=vm_library,
                                       redirect_Email=PLACEHOLDER)
        self._commands = commands
    def get_command(self, command_name):
        code = self._commands[command_name]
        

"""
class Assembler(LimitedCommandProgram):
    '''Used for creating program objects from a class'''
    @staticmethod
    def create_get_command(commands):
        def command_getter(self, command_name):
            code = commands.get(command_name, commands[''])
            if not code:
                raise RuntimeError("Command not defined in assembled program")
            def command_itself(args, state):
                return lambda old_code: code + old_code, state
            return command_itself
        return command_getter
    def _compile(args, state):
        program_name, *other_args = args.split()
        assert len(other_args) == 0
        parsed = parse_logos(state.current_buffer)
        name = ""
        commands = {'':[]}
        for command_line in parsed:
            command, parsed_args = command_line
            if command == "name" and parsed_args != "":
                name = parsed_args
            else:
                try:
                    commands[name].append(command_line)
                except KeyError:
                    commands[name] = [command_line]
        class_dict = {"get_command":Assembler.create_get_command(commands)}
        new_program = type(program_name, (LimitedCommandProgram,), class_dict)
        state.library = {program_name: new_program, **state.library}
        return None, state
    def _compile2(args, state):
        program_name, *other_args = args.split()
        assert len(other_args) == 0
        parsed = parse_logos(state.current_buffer)
        name = ""
        commands = {'':[]}
        for command_line in parsed:
            command, parsed_args = command_line
            if command == "name" and parsed_args != "":
                name = parsed_args
            else:
                try:
                    commands[name].append(command_line)
                except KeyError:
                    commands[name] = [command_line]
        class_dict = {"get_command":Assembler.create_get_command(commands)}
        new_program = type(program_name, (LimitedCommandProgram,), class_dict)
        vm_lib = state.library.copy()
        
        return None, state
    _commands = {"compile":_compile}

class FauxProgramCreator(type):
    def __new__(cls, program_name, vm_lib):
        vm = Interpreter(library=vm_lib)
        class_dict = {"get_command":FauxProgramCreator.create_get_command(commands, vm)}
        program = type(program_name, (LimitedCommandProgram,), )
    @staticmethod
    def create_get_command(commands, vm):
        def getter_command(self, command_name):
            code = commands.get(command_name, commands['']).copy()
            if not code:
                raise RuntimeError("Command not defined in assembled program")
            def command_itself(args, state):
                while code:
                    
                return None, state
            return command_itself
        return getter_command

class BaseEmailIOManager:
    def print(*args, **kwargs
"""


@dataclass
class RuntimeState:
    open_programs: dict
    current_program_name: str
    library: dict
    clipboard: str = ""
    @property
    def current_program(self):
        return self.open_programs[self.current_program_name]
    @current_program.setter
    def current_program(self, new_program):
        self.current_program_name = new_program.name()

    @property
    def current_buffer(self):
        return self.current_program.buffer
    @current_buffer.setter
    def current_buffer(self, new_buffer):
        self.current_program.buffer = new_buffer
    def clear_buffer(self):
        self.current_buffer = ""

@functional_command
def rem(args, buffer):
    #makes no changes. used for comments
    return buffer
def cut(args, state):
    assert args == "" or args == "all"
    state.clipboard = state.current_buffer
    state.clear_buffer()
    return None, state
def copy(args, state):
    assert args == "" or args == "all"
    state.clipboard = state.current_buffer
    return None, state
def paste(args, state):
    assert not args
    state.current_buffer = state.clipboard
    return None, state
def minimise(args, state):
    '''Switches to desktop.
    Name is incompatable with some locales' naming conventions, fortunately.'''
    state.current_program_name = "Desktop" #This doesn't support alternate desktops, yet.
    return None, state
def switch(args, state):
    '''Switch programs'''
    assert " " not in args #not fully Unicode supporting, but oh well
    state.current_program_name = args
    return None, state
def name(args, state):
    assert args == ""
    state.current_buffer = state.current_program_name
    return None, state
def execute(args, state):
    if args != "" and not args.endswith(" "):
        args += " "
    new_command_line = parse_logos(args + state.clipboard)
    remaining_code_changes = lambda current_code: [*new_command_line[:1], *current_code]
    return remaining_code_changes, state

safe_programs = {Email, Editor, Calculator, Terminal, Clock, Characters, Mines, Assembler}
unsafe_programs = {Files, Browser}
programs = safe_programs | unsafe_programs

KEYWORDS = {
    "rem":rem, "cut":cut, "copy":copy,
    "paste":paste, "minimise":minimise,
    "switch":switch, "name":name, "execute":execute}
STANDARD_LIBRARY = {prog.name():prog for prog in programs}
STANDARD_SANDBOX = {prog.name():prog for prog in safe_programs}

def parse_logos(text):
    text = str(text)
    if text == "":
        return []
    else:
        return parser.parse(text)

def Runtime(initial_program=Desktop, library=STANDARD_LIBRARY, *args, log_state=None, redirect_Email=None,  **kwargs):
    initial_current_program_name = initial_program.name()
    initial_library = library.copy()
    initial_program_instance = initial_program(*args, **kwargs)
    initial_open_programs = {initial_current_program_name: initial_program_instance}
    state = RuntimeState(
        initial_open_programs,
        initial_current_program_name,
        initial_library)
    #begin dispatcher/coroutine loop:
    try:
        remaining_code_changes = None
        while (command_tuple := (yield remaining_code_changes)) is not None:
            (command_name, command_args) = command_tuple
            if command_name in KEYWORDS:
                command = KEYWORDS[command_name]
            else:
                command = state.current_program.get_command(command_name)
            remaining_code_changes, state = command(command_args, state)
            if log_state is not None:
                log_state(state)
    except Exception as e:
        error_message = (f"Error while interpreting. "
            f"{command_name=} {command_args=} {state=}")
        raise RuntimeError(error_message) from e
    return

if __name__ == "__main__":
    running = Interpreter([])
    running.repl()
