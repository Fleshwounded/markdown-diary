#!/usr/bin/env python3
""" markdown-diary

TODO: Write description
"""


import os
import sys
import tempfile
import uuid
import re
import datetime
import binascii

from PyQt5 import QtGui, QtCore
from PyQt5 import QtWidgets
from PyQt5 import QtWebKitWidgets

from markdownhighlighter import MarkdownHighlighter
import markdown_math
import style


class Diary():

    def __init__(self, fname):

        self.fname = fname
        with open(fname) as f:
            self.data = f.read()
        self.checksum = binascii.crc32(bytes(self.data, encoding="UTF-8"))
        self.metadata = self.getMetadata(self.data)

    def saveDiary(self, newData):

        with open(self.fname) as f:
            data = f.read()
        checksum = binascii.crc32(bytes(data, encoding="UTF-8"))

        if checksum == self.checksum:
            newChecksum = binascii.crc32(bytes(newData, encoding="UTF-8"))

            with tempfile.NamedTemporaryFile(
                    mode="w", prefix=".diary_", suffix=".tmp",
                    dir=os.path.dirname(self.fname), delete=False) as tmpf:
                tmpf.write(newData)
            os.replace(tmpf.name, self.fname)

            self.data = newData
            self.checksum = newChecksum
            self.metadata = self.getMetadata(self.data)

        else:
            print("ERROR: Diary file was changed! Abort save.")

    def saveNote(self, note, noteId, noteDate):

        if any(noteId in metaDict["note_id"] for metaDict in self.metadata):
            self.updateNote(note, noteId, noteDate)
        else:
            newData = self.data
            noteDate = datetime.date.today().isoformat()
            noteId = noteId
            newData += self.createNoteHeader(noteId, noteDate)
            newData += note
            self.saveDiary(newData)

    def createNoteHeader(self, noteId, noteDate):

        header = ("\n<!---\n"
                  "markdown-diary note metadata\n"
                  "note_id = ")
        header += noteId
        header += "\n--->\n"
        header += noteDate
        header += "\n\n"

        return header

    def updateNote(self, note, noteId, noteDate):

        reHeader = re.compile(
            r"""^<!---
                (?:\n|\r\n)
                markdown-diary\ note\ metadata
                (?:\n|\r\n)
                note_id\ =\                     # Hashtag for PEP8 compiance
                """ + noteId +
            r"""(.*?)
                --->
                """, re.MULTILINE | re.VERBOSE | re.DOTALL)

        reHeaderNext = re.compile(
                r'^<!---(?:\n|\r\n)markdown-diary note metadata(?:\n|\r\n)',
                re.MULTILINE)

        header = reHeader.search(self.data)
        nextHeader = reHeaderNext.search(self.data, header.end())

        newData = self.data[:header.end()]
        newData += "\n"
        newData += noteDate
        newData += "\n\n"
        newData += note
        if nextHeader is not None:
            newData += "\n"
            newData += self.data[nextHeader.start():]

        self.saveDiary(newData)

    def deleteNote(self, noteId):

        reHeader = re.compile(
            r"""^<!---
                (?:\n|\r\n)
                markdown-diary\ note\ metadata
                (?:\n|\r\n)
                note_id\ =\                     # Hashtag for PEP8 compiance
                """ + noteId +
            r"""(.*?)
                --->
                """, re.MULTILINE | re.VERBOSE | re.DOTALL)

        reHeaderNext = re.compile(
                r'^<!---(?:\n|\r\n)markdown-diary note metadata(?:\n|\r\n)',
                re.MULTILINE)

        header = reHeader.search(self.data)
        nextHeader = reHeaderNext.search(self.data, header.end())

        newData = self.data[:header.start()]
        if nextHeader is not None:
            newData += "\n"
            newData += self.data[nextHeader.start():]

        self.saveDiary(newData)

    def getMetadata(self, diaryData):

        reHeader = re.compile(
            r"""^<!---                         # Beggining of Markdown comment
                (?:\n|\r\n)                    # Unix|Windows non-capturing \n
                markdown-diary\ note\ metadata # Mandatory first line
                (.*?)                          # Any characters including \n
                --->                           # End of Markdown comment
                """, re.MULTILINE | re.VERBOSE | re.DOTALL)

        matches = reHeader.finditer(diaryData)

        metadata = []
        for match in matches:
            metaDict = {}
            for line in diaryData[
                    match.start():match.end()].splitlines()[2:-1]:
                key, val = line.partition("=")[::2]
                metaDict[key.strip()] = val.strip()

            date = diaryData[match.end():].splitlines()[1]
            title = diaryData[match.end():].splitlines()[3].strip("# ")

            metaDict["date"] = date
            metaDict["title"] = title

            metadata.append(metaDict)

        return metadata

    def getNote(self, diaryData, noteId):

        reHeader = re.compile(
            r"""^<!---
                (?:\n|\r\n)
                markdown-diary\ note\ metadata
                (?:\n|\r\n)
                note_id\ =\                     # Hashtag for PEP8 compiance
                """ + noteId +
            r"""(.*?)
                --->
                (?:\n|\r\n)*
                [0-9]{4}-[0-9]{2}-[0-9]{2}      # Date in a YYYY-MM-DD format
                (?:\n|\r\n)*
                """, re.MULTILINE | re.VERBOSE | re.DOTALL)

        reHeaderNext = re.compile(
                r'^<!---(?:\n|\r\n)markdown-diary note metadata(?:\n|\r\n)',
                re.MULTILINE)

        header = reHeader.search(diaryData)
        nextHeader = reHeaderNext.search(diaryData, header.end())

        if nextHeader is None:
            return diaryData[header.end():]
        else:
            return diaryData[header.end(): nextHeader.start()]

    def getNoteMetadata(self, metadata, noteId):

        for metaDict in metadata:
            if noteId == metaDict["note_id"]:
                return metaDict


class DiaryApp(QtWidgets.QMainWindow):

    def __init__(self, parent=None):

        QtWidgets.QMainWindow.__init__(self, parent)

        renderer = markdown_math.HighlightRenderer()
        self.toMarkdown = markdown_math.MarkdownWithMath(renderer=renderer)

        self.initUI()

        self.settings = QtCore.QSettings(
                "markdown-diary", application="settings")
        self.loadSettings()

        self.loadDiary(self.recent_diaries[0])

    def __del__(self):

        pass

    def closeEvent(self, event):

        if self.text.document().isModified():
            discardMsg = ("You have unsaved changes. "
                          "Do you want to discard them?")
            reply = QtWidgets.QMessageBox.question(
                    self, 'Message', discardMsg,
                    QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No)

            if reply == QtWidgets.QMessageBox.No:
                event.ignore()
                return

        self.writeSettings()

    def initUI(self):

        self.window = QtWidgets.QWidget(self)
        self.splitter = QtWidgets.QSplitter()
        self.initToolbar()

        self.text = QtWidgets.QTextEdit(self)
        self.text.setAcceptRichText(False)
        self.text.setFont(QtGui.QFont("Ubuntu Mono"))

        self.web = QtWebKitWidgets.QWebView(self)

        # This displays incorrectly
        # self.webSettings = QtWebKit.QWebSettings.globalSettings()
        # self.webSettings.setUserStyleSheetUrl(
        #     QtCore.QUrl("file:///home/dc/bin/markdown-diary/github-markdown.css"))

        self.highlighter = MarkdownHighlighter(self.text)

        self.setCentralWidget(self.window)

        self.setWindowTitle("Markdown Diary")

        self.stack = QtWidgets.QStackedWidget()
        self.stack.addWidget(self.text)
        self.stack.addWidget(self.web)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["Id", "Date", "Title"])
        self.tree.setColumnHidden(0, True)
        self.tree.setSortingEnabled(True)
        self.tree.sortByColumn(1, QtCore.Qt.DescendingOrder)
        self.tree.itemSelectionChanged.connect(self.itemSelectionChanged)
        self.tree.itemDoubleClicked.connect(self.markdownToggle)

        self.splitter.addWidget(self.stack)
        self.splitter.addWidget(self.tree)

        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(self.splitter)

        self.window.setLayout(layout)

    def initToolbar(self):

        self.markdownAction = QtWidgets.QAction(
                QtGui.QIcon.fromTheme("down"), "Toggle Markdown", self)
        self.markdownAction.setShortcut("Ctrl+M")
        self.markdownAction.setStatusTip("Toggle markdown rendering")
        self.markdownAction.triggered.connect(self.markdownToggle)

        self.newNoteAction = QtWidgets.QAction(
                QtGui.QIcon.fromTheme("document-new"), "New note", self)
        self.newNoteAction.setShortcut("Ctrl+N")
        self.newNoteAction.setStatusTip("Create a new note")
        self.newNoteAction.triggered.connect(self.newNote)

        self.saveNoteAction = QtWidgets.QAction(
                QtGui.QIcon.fromTheme("document-save"), "Save note", self)
        self.saveNoteAction.setShortcut("Ctrl+S")
        self.saveNoteAction.setStatusTip("Save note")
        self.saveNoteAction.triggered.connect(self.saveNote)

        self.openDiaryAction = QtWidgets.QAction(
                QtGui.QIcon.fromTheme("document-open"), "Open diary", self)
        self.openDiaryAction.setShortcut("Ctrl+O")
        self.openDiaryAction.setStatusTip("Open diary")
        self.openDiaryAction.triggered.connect(self.openDiary)

        self.deleteNoteAction = QtWidgets.QAction(
                QtGui.QIcon.fromTheme("remove"), "Delete Note", self)
        self.deleteNoteAction.setShortcut("Del")
        self.deleteNoteAction.setStatusTip("Delete note")
        self.deleteNoteAction.triggered.connect(lambda: self.deleteNote())

        self.toolbar = self.addToolBar("Main toolbar")
        self.toolbar.setFloatable(False)
        self.toolbar.addAction(self.markdownAction)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.newNoteAction)
        self.toolbar.addAction(self.saveNoteAction)
        self.toolbar.addAction(self.deleteNoteAction)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.openDiaryAction)

    def loadTree(self, metadata):

        entries = []

        for note in metadata:
            entries.append(QtWidgets.QTreeWidgetItem(
                [note["note_id"], note["date"], note["title"]]))

        self.tree.clear()
        self.tree.addTopLevelItems(entries)

    def loadSettings(self):

        self.recent_diaries = ["/home/dc/bin/markdown-diary/temp/diary.md"]

        self.resize(self.settings.value(
            "window/size", QtCore.QSize(600, 400)))

        self.move(self.settings.value(
            "window/position", QtCore.QPoint(200, 200)))

        self.splitter.setSizes(list(map(int, self.settings.value(
            "window/splitter", [70, 30]))))

        toolBarArea = int(self.settings.value("window/toolbar_area",
                                              QtCore.Qt.TopToolBarArea))
        # addToolBar() actually just moves the specified toolbar if it
        # was already added, which is what we want
        self.addToolBar(QtCore.Qt.ToolBarArea(toolBarArea), self.toolbar)

        self.mathjax = self.settings.value(
                "mathjax/location",
                "https://cdn.mathjax.org/mathjax/latest/MathJax.js")

    def writeSettings(self):

        self.settings.setValue("window/size", self.size())
        self.settings.setValue("window/position", self.pos())
        self.settings.setValue("window/splitter", self.splitter.sizes())
        self.settings.setValue("window/toolbar_area", self.toolBarArea(
            self.toolbar))

    def markdownToggle(self):

        if self.stack.currentIndex() == 1:
            self.stack.setCurrentIndex(0)
        else:
            self.stack.setCurrentIndex(1)
            self.markdown()

    def markdown(self):

            html = style.css

            # We load MathJax only when there is a good chance there is
            # math in the note. We first perform inline math search as
            # as that should be faster then the re.DOTALL multiline
            # block math search, which gets executed only if we don't
            # find inline math.
            math_inline = re.compile(r"\$(.+?)\$")
            math_block = re.compile(r"^\$\$(.+?)^\$\$",
                                    re.DOTALL | re.MULTILINE)

            if (math_inline.search(self.text.toPlainText()) or
                    math_block.search(self.text.toPlainText())):

                html += style.mathjax
                mathjax_script = (
                    '<script type="text/javascript" src="{}?config='
                    'TeX-AMS-MML_HTMLorMML"></script>\n').format(self.mathjax)
                html += mathjax_script

            html += style.articleStart
            html += self.toMarkdown(self.text.toPlainText())
            html += style.articleEnd

            # Without a real file, intra-note tag links (#header1) won't work
            with tempfile.NamedTemporaryFile(
                    mode="w", prefix=".markdown-diary_", suffix=".tmp",
                    dir=tempfile.gettempdir(), delete=False) as tmpf:
                tmpf.write(html)

            # QWebView resolves relative links (like # tags) with respect to
            # the baseUrl
            self.web.setHtml(html, baseUrl=QtCore.QUrl(
                "file://" + tmpf.name))

        # TODO: Delete tmp files

    def newNote(self):

        self.noteDate = datetime.date.today().isoformat()
        self.noteId = str(uuid.uuid1())

        # TODO Add note to tree

        self.text.clear()
        self.stack.setCurrentIndex(0)

    def saveNote(self):

        self.diary.saveNote(
                self.text.toPlainText(), self.noteId, self.noteDate)
        self.text.document().setModified(False)
        self.loadTree(self.diary.metadata)

        # TODO This block is here to disallow reloading of self.text
        # which moves the cursor up. Make it more elegant than this!
        self.tree.blockSignals(True)
        self.tree.setCurrentItem(
                self.tree.findItems(self.noteId, QtCore.Qt.MatchExactly)[0])
        self.tree.blockSignals(False)

    def deleteNote(self, noteId=None):

        deleteMsg = "Do you really want to delete the note?"
        reply = QtWidgets.QMessageBox.question(
                self, 'Message', deleteMsg,
                QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No)

        if reply == QtWidgets.QMessageBox.No:
            return

        if noteId is None:
            noteId = self.noteId
        nextNoteId = self.tree.itemBelow(self.tree.currentItem()).text(0)
        self.diary.deleteNote(noteId)
        self.loadTree(self.diary.metadata)
        self.tree.setCurrentItem(
                self.tree.findItems(nextNoteId, QtCore.Qt.MatchExactly)[0])

    def openDiary(self):

        fname = QtWidgets.QFileDialog.getOpenFileName(
                caption="Open Diary",
                filter="Markdown Files (*.md);;All Files (*)")[0]

        if fname:
            if self.isValidDiary(fname):
                self.loadDiary(fname)
            else:
                print("ERROR:" + fname + "is not a valid diary file!")

    def isValidDiary(self, fname):

        # TODO Implement checks
        return True

    def loadDiary(self, fname):

        self.diary = Diary(fname)
        self.loadTree(self.diary.metadata)

        lastNoteId = self.diary.metadata[-1]["note_id"]
        self.tree.setCurrentItem(
                self.tree.findItems(lastNoteId, QtCore.Qt.MatchExactly)[0])
        self.stack.setCurrentIndex(1)

    def itemSelectionChanged(self):

        if self.text.document().isModified():
            discardMsg = ("You have unsaved changes. "
                          "Do you want to discard them?")
            reply = QtWidgets.QMessageBox.question(
                    self, 'Message', discardMsg,
                    QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No)

            if reply == QtWidgets.QMessageBox.No:
                self.tree.blockSignals(True)
                self.tree.setCurrentItem(self.tree.findItems(
                            self.noteId, QtCore.Qt.MatchExactly)[0])
                self.tree.blockSignals(False)
                return

        if len(self.tree.selectedItems()) != 1:
            return

        item = self.tree.selectedItems()[0]
        self.displayNote(item.text(0))

    def displayNote(self, noteId):

        self.text.setText(self.diary.getNote(self.diary.data, noteId))
        self.noteId = noteId
        self.noteDate = self.diary.getNoteMetadata(
                self.diary.metadata, noteId)["date"]
        self.markdown()


def main():

    app = QtWidgets.QApplication(sys.argv)

    main = DiaryApp()
    main.show()

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
