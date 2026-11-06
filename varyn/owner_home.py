"""VARYN local owner home: a usable AI, tasks, integration directory UI.

Normal Windows launcher opens this window. Each AI dispatch remains behind
existing approval gates. Tasks are local SQLite metadata, not an executor.
"""
import os
from pathlib import Path
import sqlite3
import tkinter as tk
from tkinter import ttk

from varyn.integration_catalog import load_catalog, CatalogRejected
from varyn.unlimited_task_store import TaskStore, TaskRejected


def owner_task_path():
    base = os.environ.get("LOCALAPPDATA")
    folder = Path(base) if base else Path.home() / "AppData" / "Local"
    folder = folder / "VARYN"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "tasks.sqlite3"


class OwnerHome(tk.Toplevel):
    def __init__(self, desktop, *, database_path=None):
        super().__init__(desktop)
        self.desktop = desktop
        self.closed = False
        self.tick_id = None
        self.offset = 0
        self.store = None
        self.title("VARYN | AI, Tasks and Integrations")
        self.geometry("900x640")
        self.minsize(650, 450)
        self.transient(desktop)
        try:
            self.store = TaskStore(database_path or owner_task_path())
            self._build()
            self.refresh()
            self.tick_id = self.after(30000, self._tick)
        except BaseException:
            if self.store is not None:
                self.store.close()
            self.destroy()
            raise
        self.protocol("WM_DELETE_WINDOW", self.close)

    def _build(self):
        shell = ttk.Frame(self, padding=14)
        shell.pack(fill="both", expand=True)
        ttk.Label(shell, text="VARYN | Personal AI Workspace",
                  font=("Segoe UI", 17, "bold")).pack(anchor="w")
        ttk.Label(shell, wraplength=820, text=(
            "Experimental local Windows alpha. Real AI requests use your own API key "
            "and explicit approval; tasks and integration directory work offline."
        )).pack(anchor="w", pady=(4, 12))
        tabs = ttk.Notebook(shell)
        tabs.pack(fill="both", expand=True)
        ai, tasks, apps = (ttk.Frame(tabs, padding=12) for _ in range(3))
        tabs.add(ai, text="Ask AI")
        tabs.add(tasks, text="My Tasks")
        tabs.add(apps, text="Connectors / Skills")
        ttk.Label(ai, text="Ask a real AI model or test offline",
                  font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=6)
        ttk.Label(ai, wraplength=730, text=(
            "The Model Control Center can route one reviewed request to OpenRouter, "
            "DeepSeek or authorized local 9Router. No key? Try the fake model offline. "
            "Prices are your estimates, not provider billing caps."
        )).pack(anchor="w")
        ttk.Button(ai, text="Open Model Control Center",
                   command=self._model).pack(anchor="w", pady=14)
        ttk.Button(ai, text="Manual ChatGPT / Claude / Gemini handoff",
                   command=self._relay).pack(anchor="w")
        ttk.Label(ai, text="Official-app handoff requires manual copy/paste, not account sync.",
                  wraplength=700).pack(anchor="w", pady=8)

        ttk.Label(tasks, text="Owner-local task board",
                  font=("Segoe UI", 13, "bold")).pack(anchor="w")
        ttk.Label(tasks, wraplength=790, text=(
            "Tasks are saved in unencrypted local SQLite. Due status refreshes every "
            "30 seconds while this app is open. No task runs automatically and "
            "there is no artificial total task count limit."
        )).pack(anchor="w", pady=(3,8))
        form = ttk.Frame(tasks)
        form.pack(fill="x")
        self.title_var = tk.StringVar(master=self)
        self.due_var = tk.StringVar(master=self)
        ttk.Label(form, text="Task title").grid(row=0,column=0,sticky="w")
        ttk.Label(form, text="Due: ISO with timezone (optional)").grid(row=0,column=1,sticky="w")
        ttk.Entry(form, textvariable=self.title_var).grid(row=1,column=0,sticky="ew")
        ttk.Entry(form, textvariable=self.due_var, width=29).grid(row=1,column=1,sticky="ew",padx=6)
        ttk.Button(form,text="Add",command=self.add).grid(row=1,column=2)
        form.columnconfigure(0,weight=3)
        form.columnconfigure(1,weight=2)
        ttk.Label(tasks,text="Example: 2026-11-09T14:30:00+07:00").pack(anchor="w",pady=(2,5))
        self.table=ttk.Treeview(tasks,columns=("title","status","due"),show="headings",
                                height=9,selectmode="browse")
        for key,label,w in (("title","Task",380),("status","Status",100),("due","Due UTC",230)):
            self.table.heading(key,text=label)
            self.table.column(key,width=w,stretch=(key=="title"),minwidth=70)
        self.table.pack(fill="both",expand=True,pady=(0,6))
        actions=ttk.Frame(tasks)
        actions.pack(fill="x")
        for label,state in (("Complete","completed"),("Pause","paused"),("Cancel","cancelled")):
            ttk.Button(actions,text=label,command=lambda s=state:self.change(s)).pack(side="left",padx=(0,5))
        ttk.Button(actions,text="Refresh",command=self.refresh).pack(side="left")
        ttk.Button(actions,text="Next",command=lambda:self.page(1)).pack(side="right")
        ttk.Button(actions,text="Previous",command=lambda:self.page(-1)).pack(side="right",padx=5)
        self.feedback=tk.StringVar(master=self,value="")
        ttk.Label(tasks,textvariable=self.feedback,wraplength=790).pack(anchor="w",pady=6)

        ttk.Label(apps,text="Integration catalog (NOT CONNECTED)",
                  font=("Segoe UI",13,"bold")).pack(anchor="w")
        ttk.Label(apps,wraplength=790,text=(
            "The following connector, plugin and skill names are discovery entries, "
            "not authenticated integrations. Existing ChatGPT account connections "
            "cannot be copied into VARYN."
        )).pack(anchor="w",pady=(3,8))
        tree=ttk.Treeview(apps,columns=("kind","name","status"),show="headings",height=12)
        for key,label,w in (("kind","Type",155),("name","App / skill",350),("status","Availability",170)):
            tree.heading(key,text=label)
            tree.column(key,width=w,minwidth=75,stretch=(key=="name"))
        tree.pack(fill="both",expand=True)
        try:
            entries=load_catalog()
        except (CatalogRejected,OSError):
            entries=()
            ttk.Label(apps,text="Bundled catalog unavailable. No connection attempted.").pack(anchor="w")
        for index,item in enumerate(entries):
            tree.insert("","end",iid="c-"+str(index),
                        values=(item.kind,item.name,"NOT CONNECTED"))
        ttk.Button(apps,text="Open advanced desktop tools",
                   command=self._advanced).pack(anchor="w",pady=8)
        ttk.Label(shell,wraplength=790,text=(
            "No native ChatGPT/Claude/Gemini history sync, no automatic connector "
            "execution, no production confidentiality guarantees."
        )).pack(anchor="w",pady=(8,0))

    def _model(self):
        if self.closed or self.desktop._closing:return
        self.desktop._open_model_control_center()
        panel=self.desktop._model_center
        if panel is not None and panel.winfo_exists():
            panel.lift()
            panel.focus_set()

    def _relay(self):
        if self.closed or self.desktop._closing:return
        self.desktop._open_relay_workbench()
        panel=self.desktop._relay_workbench
        if panel is not None and panel.winfo_exists():panel.lift()

    def _advanced(self):
        if self.closed or self.desktop._closing:return
        self.desktop.deiconify()
        self.desktop.lift()

    def add(self):
        if self.closed:return
        try:
            self.store.create(self.title_var.get(),due_utc=self.due_var.get().strip() or None)
            self.title_var.set("")
            self.due_var.set("")
            self.offset=0
            self.refresh()
            self.feedback.set("Task saved on this PC. No external action performed.")
        except (TaskRejected,OSError,sqlite3.Error):
            self.feedback.set("Invalid title or due date. Include timezone, e.g. +07:00.")

    def change(self,status):
        if self.closed:return
        picked=self.table.selection()
        if not picked:
            self.feedback.set("Select a task first.")
            return
        try:
            self.store.transition(picked[0],status)
            self.refresh()
            self.feedback.set("Task marked "+status+" locally; no external action.")
        except (TaskRejected,OSError,sqlite3.Error):
            self.feedback.set("Cannot change this task's current status.")

    def page(self,delta):
        self.offset=max(0,self.offset+delta*100)
        self.refresh()

    def refresh(self):
        if self.closed:return
        try:
            total=self.store.count()
            if self.offset>=total:
                self.offset=(max(0,total-1)//100)*100
            rows=self.store.list(limit=100,offset=self.offset)
            for iid in self.table.get_children():self.table.delete(iid)
            for item in rows:
                self.table.insert("","end",iid=item["id"],
                                  values=(item["title"],item["status"],
                                          item["due_utc"] or "not scheduled"))
            self.feedback.set(
                str(total)+" saved tasks | showing "+str(len(rows))+
                " | due checked every 30s while open; never executed.")
        except (TaskRejected,OSError,sqlite3.Error):
            self.feedback.set("Local task store unavailable; no task dispatched.")

    def _tick(self):
        self.tick_id=None
        if self.closed or self.desktop._closing:return
        try:
            updated=self.store.mark_due(batch_size=200)
            if updated:self.refresh()
        except (TaskRejected,OSError,sqlite3.Error):
            self.feedback.set("Due refresh failed. No task executed.")
        self.tick_id=self.after(30000,self._tick)

    def close(self):
        if self.closed:return
        self.closed=True
        if self.tick_id is not None:
            try:self.after_cancel(self.tick_id)
            except tk.TclError:pass
            self.tick_id=None
        if self.store is not None:
            self.store.close()
            self.store=None
        self.destroy()
