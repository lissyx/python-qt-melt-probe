#!/usr/bin/python
# -*- coding: utf-8 -*-
# vim: set ts=4 sw=4 et:

"""
MELT probe in PyQt
"""

import sys
import os
import argparse
import select
import pprint
from datetime import datetime
from threading import Thread
from PyQt4.QtGui import *
from PyQt4.QtCore import *
from PyQt4.Qsci import *

MELT_SIGNAL_UNHANDLED_COMMAND = SIGNAL("unhandledCommand(PyQt_PyObject)")
MELT_SIGNAL_DISPATCH_COMMAND = SIGNAL("dispatchCommand(PyQt_PyObject)")
MELT_SIGNAL_APPEND_TRACE_COMMAND = SIGNAL("appendCommand(PyQt_PyObject)")
MELT_SIGNAL_APPEND_TRACE_REQUEST = SIGNAL("appendRequest(PyQt_PyObject)")
MELT_SIGNAL_SOURCE_SHOWFILE = SIGNAL("sourceShowfile(PyQt_PyObject)")
MELT_SIGNAL_SOURCE_MARKLOCATION = SIGNAL("sourceMarklocation(PyQt_PyObject)")
MELT_SIGNAL_SOURCE_INFOLOCATION = SIGNAL("sourceInfoLocation(PyQt_PyObject)")
MELT_SIGNAL_ASK_INFOLOCATION = SIGNAL("askInfoLocation(PyQt_PyObject)")

MELT_SIGNAL_SOURCE_STARTINFOLOC = SIGNAL("startInfoLocation(PyQt_PyObject)")
MELT_SIGNAL_SOURCE_ADDINFOLOC = SIGNAL("addInfoLocation(PyQt_PyObject)")

class MeltSourceViewer(QsciScintilla):
    ARROW_MARKER_NUM = 8
    indicators = {}

    def __init__(self, parent, obj):
        QsciScintilla.__init__(self, parent)

        self.file = obj
        self.setReadOnly(True)
        self.setObjectName("MeltSourceViewer:" + self.file['filename'])
        self.indicator = self.indicatorDefine(QsciScintilla.BoxIndicator)

        # Set the default font
        font = QFont()
        font.setFamily('Courier')
        font.setFixedPitch(True)
        font.setPointSize(10)
        ## self.setFont(font)
        self.setMarginsFont(font)

        # Margin 0 is used for line numbers
        fontmetrics = QFontMetrics(font)
        self.setMarginsFont(font)
        self.setMarginWidth(0, fontmetrics.width("00000") + 6)
        self.setMarginLineNumbers(0, True)
        self.setMarginsBackgroundColor(QColor("#cccccc"))

        # Clickable margin 1 for showing markers
        self.setMarginSensitivity(1, False)
        # self.connect(self,
        #    SIGNAL('marginClicked(int, int, Qt::KeyboardModifiers)'),
        #    self.on_margin_clicked)
        self.markerDefine(QsciScintilla.RightArrow,
            self.ARROW_MARKER_NUM)
        self.setMarkerBackgroundColor(QColor("#ee1111"),
            self.ARROW_MARKER_NUM)

        self.connect(self,
            SIGNAL('indicatorClicked(int, int, Qt::KeyboardModifiers)'),
            self.on_indicator_clicked)

        # Brace matching: enable for a brace immediately before or after
        # the current position
        #
        self.setBraceMatching(QsciScintilla.SloppyBraceMatch)

        # Current line visible with special background color
        self.setCaretLineVisible(True)
        self.setCaretLineBackgroundColor(QColor("#ffe4e4"))

        # Set lexer
        # Set style for Python comments (style number 1) to a fixed-width
        # courier.
        #
        ## lexer.setDefaultFont(font)
        self.setLexer(self.select_lexer(self.file['filename']))
        ## self.SendScintilla(QsciScintilla.SCI_STYLESETFONT, 1, 'Courier')

        # Don't want to see the horizontal scrollbar at all
        # Use raw message to Scintilla here (all messages are documented
        # here: http://www.scintilla.org/ScintillaDoc.html)
        self.SendScintilla(QsciScintilla.SCI_SETHSCROLLBAR, 0)

        # not too small
        self.setMinimumSize(600, 450)

        self.append(self.read_file(self.file['filename']))

    def get_filenum(self):
        return self.file['filenum']

    def select_lexer(self, filename):
        lexer = QsciLexerBash()
        fname, ext = os.path.splitext(filename)

        if ext == ".c" or ext == ".cpp" or ext == ".h" or ext == ".hpp":
            lexer = QsciLexerCPP()

        return lexer

    def read_file(self, filename):
        if filename == "<built-in>":
            return "Pseudo file, built-in."

        content = ""
        with open(filename) as f:
            content = f.readlines()
        return "".join(content)

    def mark_location(self, o):
        lineFrom = o['line']
        indexFrom = o['col']
        lineTo = o['line']
        indexTo = o['col'] + 1
        self.indicators[str(lineFrom) + ":" + str(indexFrom)] = o
        self.fillIndicatorRange(lineFrom, indexFrom, lineTo, indexTo, self.indicator)
        self.markerAdd(lineFrom, self.ARROW_MARKER_NUM)
        # print self.file['filename'], "::adding marker on line", lineFrom

    def on_margin_clicked(self, nmargin, nline, modifiers):
        # Toggle marker for the line the margin was clicked on
        if self.markersAtLine(nline) != 0:
            self.markerDelete(nline, self.ARROW_MARKER_NUM)
        else:
            self.markerAdd(nline, self.ARROW_MARKER_NUM)

    def on_indicator_clicked(self, line, index, state):
        # print "on_indicator_clicked(", self, ", ", line, ", ", index, ", ", state, ")"
        indic = self.indicators[str(line) + ":" + str(index)]
        self.emit(MELT_SIGNAL_SOURCE_INFOLOCATION, indic)

    def slot_marklocation(self, o):
        if (self.file['filenum'] == o['filenum']):
            self.mark_location(o)

    def slot_startinfolocation(self, o):
        if (self.file['filenum'] == o['filenum']):
            print "slot_startinfolocation(", o,")"

    def slot_addinfolocation(self, o):
        if (self.file['filenum'] == o['filenum']):
            print "slot_addinfolocation(", o,")"

class MeltCommandDispatcher(QObject):
    FILES = {}
    MARKS = {}

    def __init__(self):
        QObject.__init__(self)

    def slot_unhandledCommand(self, cmd):
        print "E: Unhandled command:", cmd

    def slot_dispatchCommand(self, comm):
        print "Dispatcher receive:", comm

        o = comm.split(" ")
        self.emit(MELT_SIGNAL_APPEND_TRACE_COMMAND, o)

        sig = MELT_SIGNAL_UNHANDLED_COMMAND
        obj = o
        cmd = o[0]
        if cmd == "SHOWFILE_PCD":
            fnum = int(o[4])
            obj = {'command': 'showfile', 'filename': o[2].strip('"'), 'filenum': fnum}
            sig = MELT_SIGNAL_SOURCE_SHOWFILE
            if not self.FILES.has_key(fnum):
                self.FILES[fnum] = {'file': obj, 'marks': {}}
        elif cmd == "MARKLOCATION_PCD":
            # -1 pour corriger l'affichage
            marknum = int(o[1])
            filenum = int(o[2])
            obj = {'command': 'marklocation', 'marknum': marknum, 'filenum': filenum, 'line': max(int(o[3]) - 1, 0), 'col': max(int(o[4]) - 1, 0)}
            sig = MELT_SIGNAL_SOURCE_MARKLOCATION
            if not self.MARKS.has_key(marknum):
                self.MARKS[marknum] = filenum
                self.FILES[filenum]['marks'][marknum] = obj
        elif cmd == "STARTINFOLOC_PCD":
            marknum = int(o[1])
            filenum = self.MARKS[marknum]
            obj = {'command': 'startinfoloc', 'marknum': marknum, 'filenum': filenum}
            sig = MELT_SIGNAL_SOURCE_STARTINFOLOC
        elif cmd == "ADDINFOLOC_PCD":
            marknum = int(o[1])
            filenum = self.MARKS[marknum]
            obj = {'command': 'addinfoloc', 'marknum': marknum, 'filenum': filenum, 'payload': " ".join(o[2:]).split('"   "')}
            sig = MELT_SIGNAL_SOURCE_ADDINFOLOC

        print "Dispatcher emit:", sig, obj

        self.emit(sig, obj)

    def slot_sendInfoLocation(self, obj):
        self.emit(MELT_SIGNAL_ASK_INFOLOCATION, "INFOLOCATION_prq " + str(obj['marknum']))

class MeltCommunication(QObject, Thread):
    def __init__(self, fdin, fdout):
        QObject.__init__(self)
        Thread.__init__(self)
        self.melt_stdout = fdin
        self.melt_stdin  = fdout

        self.epoll = select.epoll()
        self.epoll.register(self.melt_stdout, select.EPOLLIN)

        self.buf = ""

    def run(self):
        print "I'm", self.getName()
        try:
            while True:
                events = self.epoll.poll(1)
                for fileno, event in events:
                    if event & select.EPOLLIN:
                        c = os.read(fileno, 1)
                        if c == '\n':
                            if len(self.buf) > 0:
                                self.command = self.buf
                                self.emit(MELT_SIGNAL_DISPATCH_COMMAND, self.command)
                            self.buf = ""
                        else:
                            self.buf += c
                    elif event & select.EPOLLOUT:
                        print "READY TO WRITE"
                    elif event & select.EPOLLHUP:
                        self.epoll.unregister(fileno)
        finally:
            self.epoll.unregister(self.melt_stdout)
            self.epoll.close()

    def send_melt_command(self, str):
        self.emit(MELT_SIGNAL_APPEND_TRACE_REQUEST, str)
        return os.write(self.melt_stdin, str + "\n\n")

    def slot_sendInfoLocation(self, cmd):
        self.send_melt_command(cmd)

class MeltTraceWindow(QMainWindow, Thread):
    def __init__(self):
        Thread.__init__(self)
        super(MeltTraceWindow, self).__init__()
        self.initUI()

    def initUI(self):
        self.text = QTextEdit()
        self.setCentralWidget(self.text)
        self.setGeometry(0, 0, 640, 480)
        self.setWindowTitle("MELT Trace Window")
        self.show()

    def run(self):
        print "I'm", self.getName()
        pass

    def slot_appendCommand(self, command):
        str = "<font color=\"gray\">%(date)s</font><br /><font color=\"blue\">%(command)s</font><br />" % {'date': datetime.isoformat(datetime.now()), 'command': " ".join(command)}
        self.text.append(str)

    def slot_appendRequest(self, command):
        str = "<font color=\"gray\">%(date)s</font><br /><font color=\"red\">%(command)s</font><br />" % {'date': datetime.isoformat(datetime.now()), 'command': command}
        self.text.append(str)

class MeltSourceWindow(QMainWindow, Thread):
    def __init__(self, dispatcher, comm):
        Thread.__init__(self)
        super(MeltSourceWindow, self).__init__()
        self.dispatcher = dispatcher
        self.comm = comm
        self.filemaps = {}
        self.initUI()

        QObject.connect(self.dispatcher, MELT_SIGNAL_SOURCE_SHOWFILE, self.slot_showfile, Qt.QueuedConnection)

    def initUI(self):
        window = QWidget()
        self.tabs = QTabWidget()
        self.vlayout = QVBoxLayout()
        self.vlayout.addWidget(self.tabs)
        window.setLayout(self.vlayout)
        window.show()
        self.setCentralWidget(window)
        self.setGeometry(0, 0, 640, 480)
        self.setWindowTitle("MELT Source Window")
        self.show()

    def run(self):
        print "I'm", self.getName()
        pass

    def get_filename(self, path):
        (dir, fname) = os.path.split(path)
        return fname

    def slot_showfile(self, o):
        qw = QWidget()
        layout = QVBoxLayout()
        qw.setLayout(layout)

        if os.path.exists(o['filename']) or o['filename'] == "<built-in>":
            txt = MeltSourceViewer(qw, o)
            lbl = QLabel(o['filename'])
            QObject.connect(self.dispatcher, MELT_SIGNAL_SOURCE_MARKLOCATION, txt.slot_marklocation, Qt.QueuedConnection)
            QObject.connect(txt, MELT_SIGNAL_SOURCE_INFOLOCATION, self.dispatcher.slot_sendInfoLocation, Qt.QueuedConnection)
            QObject.connect(self.dispatcher, MELT_SIGNAL_SOURCE_STARTINFOLOC, txt.slot_startinfolocation, Qt.QueuedConnection)
            QObject.connect(self.dispatcher, MELT_SIGNAL_SOURCE_ADDINFOLOC, txt.slot_addinfolocation, Qt.QueuedConnection)
            layout.addWidget(lbl)
            layout.addWidget(txt)
            self.tabs.addTab(qw, "[%(fnum)s] %(filename)s" % {'fnum': o['filenum'], 'filename': self.get_filename(o['filename'])})
            self.filemaps[o['filenum']] = qw
            # print "mapping",o['filenum'],"with object:",txt.objectName()
        else:
            print "Unable to open '%(file)s'" % {'file': o['filename']}
            return
            err = QErrorMessage("Unable to open '%(file)s'" % {'file': o['filename']})
            err.showMessage()

class MeltProbeApplication(QApplication):
    TRACE_WINDOW = None
    SOURCE_WINDOW = None

    def __init__(self):
        self.app = QApplication(sys.argv)
        self.parse_args()
        self.main()

    def main(self):
        dispatcher = MeltCommandDispatcher()
        comm = MeltCommunication(self.args.command_from_MELT, self.args.request_to_MELT)
        if (self.args.T):
            self.TRACE_WINDOW = MeltTraceWindow()
            self.TRACE_WINDOW.start()
        self.SOURCE_WINDOW = MeltSourceWindow(dispatcher, comm)
        self.SOURCE_WINDOW.start()

        QObject.connect(comm, MELT_SIGNAL_DISPATCH_COMMAND, dispatcher.slot_dispatchCommand, Qt.QueuedConnection)
        QObject.connect(dispatcher, MELT_SIGNAL_ASK_INFOLOCATION, comm.slot_sendInfoLocation, Qt.QueuedConnection)

        if (self.args.T):
            QObject.connect(dispatcher, MELT_SIGNAL_APPEND_TRACE_COMMAND, self.TRACE_WINDOW.slot_appendCommand, Qt.QueuedConnection)
            QObject.connect(comm, MELT_SIGNAL_APPEND_TRACE_REQUEST, self.TRACE_WINDOW.slot_appendRequest, Qt.QueuedConnection)

        QObject.connect(dispatcher, MELT_SIGNAL_UNHANDLED_COMMAND, dispatcher.slot_unhandledCommand, Qt.QueuedConnection)

        comm.start()
        sys.exit(self.app.exec_())

    def parse_args(self):
        self.parser = argparse.ArgumentParser(description="MELT probe")
        self.parser.add_argument("-T", action="store_true", required=False, help="Tracing mode")
        self.parser.add_argument("-D", action="store_true", required=False, help="Debug mode")
        self.parser.add_argument("--command-from-MELT", type=int, required=True, help="FD to read from")
        self.parser.add_argument("--request-to-MELT", type=int, required=True, help="FD to write to")
        self.args = self.parser.parse_args()

if __name__ == '__main__':
    mpa = MeltProbeApplication()
