# logOS
Programming language inspired by desktop operating systems.

Interpreter runs on Python 3.8+.

Esolangs page [here](https://esolangs.org/wiki/logOS).

## Introduction

We human meatbags often have trouble thinking as abstractly as
computers. It helps to have an analogy: "Just think of your files as
physical documents, grandma. You can write words in them, and categorise
them by putting them in folders. And they all sit there on your
desktop."

That idea is the Desktop Metaphor, an analogy that has persisted since
1970, because it's easy to understand. Even the maddest of hatters knows
how a writing desk works. Could we not bring some of those magical
metaphors into the incomprehensible world of computer programming? This
innovation leads us to logOS, a language designed to mimic a desktop
computer as much as possible.

We reify complex control flow and data processing procedures into the
simple language of using a computer. You cut and paste text, pull out
your nifty calculator program, switch to your email manager... all
things the average user does on a daily basis.

## Understanding the Basic Concepts

(This section should be simple to understand.)

### Overview

A procedure in logOS will often consist of cutting and pasting data into
different programs in order to manipulate it.

All data is text. You can represent anything, from a number to a novel,
in that format. What your text is treated as depends on what commands
you run.

### Programs

Programs, the bread and butter of the language, have a field that stores
text, and commands that change what the program stores. For example, if
you write "2 + 2" into Calculator, and use the "=" command, it'll
replace your expression with "4". Easy!

There is one active program at a time. This is the program that's
currently in use. To use a different one, you'll need to switch to that
program, or start it up if it isn't already open. Note that only one
instance of each program can be open at once. Otherwise switching
between programs could get confusing.

Programs will generally only store their current state in their text
field, which we call a 'buffer'. For example, Editor (a text editor)
will store the document you are editing in its buffer.

The functionality of programs comes from their commands, which change
the buffer in some way.

### Commands

Commands are the individual features a program implements. (If you are a
programmer, these are like the methods of an object.) Whenever you run a
command, the buffer of the program will change. In our Calculator
example, the "=" command changed our buffer, "2 + 2" to the result, "4".
Commands can also have parameters. An example is the "+" command in our
calculator: with "4" in Calculator's buffer, "+ 3" will add 3 to 4, and
replace the buffer with the answer. The exact result is left as an
exercise for the reader.

The instructions to logOS are lines of code. The first word of each line
is a command, and anything afterwards is the arguments of the command.
The space directly after the command is ignored, but any spaces after
that are passed faithfully to the command, until the end of the line.

Certain reserved commands will work anywhere, no matter what program is
active. For example, you can always copy, paste, and minimise.

### Buffers and Clipboard

Each program stores one arbitrary length string while it remains
running. The buffer persists if you switch to another program then
switch back, and can store any Unicode characters.

In order to move text from one program to another, logOS has a
clipboard. You can cut or copy text to put data into your clipboard.
(The former command deletes the buffer in the process, while the latter
preserves it.) Then, you can paste it into a different program;
clipboard text persists until you cut or copy something new, no matter
which programs you switch between.

### The Desktop

When you minimise or close a program, you are shunted to the desktop.
This purgatory state facilitates opening programs. Any command other
than a reserved keyword will open the program with that name. Any
command, although that might leave you wondering about what happens in
the event of nonexistence of that program.

The answer is that it opens a note, an inert program whose only purpose
is to store text. For example, running the command "ShoppingList" from
the desktop will allow me to store text in the buffer of ShoppingList,
even though ShoppingList isn't a real program. ShoppingList has no
commands implemented, but from that point onwards, ShoppingList is
technically a program you can switch to and from. (Notes are the
equivalent of variables, for all you tech whizzes reading this.)

## Useful Programs

### Email

This program is used for communication with the user. "send" will
display the buffer as text to the user, while "refresh" will wait for a
communication from the user, in the form of a line of text.

### Editor

Used for manipulating text as a collection of characters and words.
'write "X"' will append X to the buffer, or a newline if no arguments
are passed, for which purpose you can also use "write a newline" or
"write newline". Something similar happens for writing a quotemark,
although you can also use a literal double quotemark there, '"'.
"backspace" will delete the last character of the buffer, unless it is
passed "word" or "line" in which case it will remove that much. You can
also specify a number, e.g. "backspace 3", "backspace 1 words", or
"backspace 3 characters". Note that if a number is specified, even if
the number is 1, you must pluralise the unit. For instance, "backspace 1
word" will not work. 'replace "X" with "Y"' will perform that
replacement on the buffer, but will fail unless there are quote marks
around the values you want replaced; you can instead use the unquoted
strings "a newline" and "newline" as specifiers, which also works for
"quotemark" and similar. "count", "count words" and 'count "The"' will
do as you'd expect, counting how many times the unit or string appears
in the buffer, then replacing the buffer with that number. "append the
clipboard" will take the clipboard and append it to the end of the
buffer, leaving the clipboard empty. "tailor" accepts the same arguments
as "backspace", except it leaves behind the tail of the text, rather
than removing the tail of the text, so it can be used to select just the
last part of a buffer.

### Calculator

Used for numerical arithmetic. The command "=" will perform the
calculation specified by its buffer, as long as each operator is one of
"+", "-", "\*", "/" or "^". The latter is for exponents. Order of
operations and brackets are respected. Those operators may also be used
as commands, and must be passed another number. Numbers must be in
integer or float format, and scientific notation is supported.

### Terminal

Used for control flow. "run" will replace the rest of the code that is
currently running with the buffer of the program. It will also wipe the
buffer in the process.

### Files

Used for accessing files and folders on the actual operating system, not
the emulated one. The commands all take a path in Unix format, i.e. with
forward slashes. (We may be simulating a Windows-like operating system,
but path format is a matter of principle.) "create", "delete", "create
the folder at" and "delete the folder at" do as specified, the former
two operating on files rather than folders, and all taking a path as
their last parameter. "load" and "save" are used to save and load the
buffer to the specified path.

### Browser

"navigate to", when run with a URL as its parameter, will send a POST
request to that URL, or GET with an empty buffer, over HTTPS. If the
buffer is not empty, it will be used as the data. The response will be
stored in the buffer. Headers may not be spoofed. In order to perform
requests asynchronously, you will need to perform a "wait" command using
Clock, in order to wait until asynchrony is added to this language.

### Clock

"wait" will wait a number of seconds specified in the buffer, or
milliseconds or minutes as specified. "time" will replace the buffer
with the current time, in a human readable format. "time in terms of
unix epoch" will do the same, except using the Unix epoch, and "time in
terms of utc" is pretty obvious too. The format of the non-Unix modes is
"2 seconds past 9:06 AM on Monday the 3rd of August, 2019"

### Characters

"Unicode" will convert a codepoint in the form of a denary number into a
character, or multiple numbers separated by spaces into multiple
characters. "codepoints" does the reverse.

### Mines

"generate X" will generate X squares, where each square has a 50% chance
of being a mine. The entire minesweeping grid is condensed into one
line, with mines and empty spaces being represented by 1s and 0s
respectively.

### Solitaire

Used for reordering lines. "sort lexicographically" sorts
lexicographically by Unicode codepoints. "sort alphabetically" is the
same, but performs a casefold operation first. "sort numerically" sorts
numerically. "sort lexicographically in descending order" does what
you'd expect. "lexicographically" can be omitted because it's the
default.

(Not Implemented)

### Assembler

"compile X" turns command declarations into a program named X. Command
declarations contain instructions to perform on the input and are
separated by "name Y" where Y is the name of the command. Convention is
to put a newline after each command declaration, and for commands to not
permanently alter the state of other programs, or the clipboard. (The
exception to this is that programs may close note programs that have the
program name as a prefix.)

(Half Implemented)

### Python

"eval" will eval the buffer in Python, in the same Python instance as is
running the interpreter. Be careful with it.

(Not Implemented)

If you are irritated that the spec doesn't entirely match the reference
interpreter, I, IFcoltransG, welcome pull requests on the interpreter
and suggestions on the spec.

## Reserved Keywords

### cut

Transfers all text in the buffer into the clipboard.

### copy

Duplicates all text in the buffer into the clipboard.

### paste

Duplicates all text in the clipboard into the buffer.

### minimise

Switches to the Desktop.

### switch

Switches to an open program.

### name

Replaces the current buffer in its entirety with the name of the active
program. Also used to declare a command name in user defined programs
e.g. "name foo" followed by the code for that command.

### execute

Runs the current clipboard as if it were a line of code. This allows you
to create complex commands that depend on the results of other commands.
Any arguments to the keyword are prepended to the command before it is
executed.

### rem

Used for comments. Will ignore its argument.

Note: this specification is available under the [<u>CC0 1.0 Universal
Public Domain
Dedication</u>](http://creativecommons.org/publicdomain/zero/1.0/) which
should allow you to freely copy it elsewhere. There's no warranty
either; if you have a problem, take it up with your conscience.
