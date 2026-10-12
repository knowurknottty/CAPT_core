"""Human-facing Council Workflow Builder.

The UI configures exact cohort geometry and provider/model assignments, then
uses the shared Operator facade for governed approval and execution. It never
mints authority locally and never auto-approves.
"""
from __future__ import annotations

import argparse
import json
import os
import queue
import threading
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from capt_ui.operator.council_workflow import (
    CohortWorkflow,
    CouncilWorkflow,
    donor_convergence_workflow,
)
from capt_ui.operator.runtime import Operator, OperatorError


def render_headless(workflow: CouncilWorkflow) -> str:
    workflow.validate()
    return json.dumps(workflow.to_record(), sort_keys=True, separators=(",", ":"))


def _defaults() -> tuple[str, str]:
    state = Path.home() / ".capt"
    return str(state / "runtime.sock"), str(state / "runtime.token")


def _friendly_error(exc: BaseException) -> str:
    message = str(exc)
    if "IPC_FRAME_JSON_INVALID" in message:
        return (
            "The runtime IPC stream became desynchronized. CAPT now serializes "
            "GUI/background requests to prevent this; reconnect the Council window "
            "and retry if this came from an older open client."
        )
    if "connection closed by runtime" in message.lower():
        return "The CAPT runtime connection closed. Reopen the Council window after RuntimeService is healthy."
    return message


def run_window(sock: str, token_file: str, target_root: str = "") -> None:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    op = Operator(sock, token_file)
    op.connect()

    root = tk.Tk()
    root.title("CAPT · Model Council — Recovery R3")
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    width = max(1040, min(1480, screen_w - 64))
    height = max(720, min(900, screen_h - 96))
    root.geometry(f"{width}x{height}+{max(20, (screen_w-width)//2)}+{max(28, (screen_h-height)//3)}")
    root.minsize(min(1040, width), min(720, height))

    style = ttk.Style(root)
    style.configure("CouncilHero.TLabel", font=("Helvetica", 20, "bold"))
    style.configure("CouncilSub.TLabel", font=("Helvetica", 11))
    style.configure("CouncilSummary.TLabel", font=("Helvetica", 11, "bold"))

    header = ttk.Frame(root, padding=(12, 10, 12, 4))
    header.pack(fill="x")
    ttk.Label(header, text="Model Council", style="CouncilHero.TLabel").pack(side="left")
    ttk.Label(
        header,
        text="  Human-configured cohorts · governed approval · HTTP requests may exceed cohort count",
        style="CouncilSub.TLabel",
    ).pack(side="left", padx=(8, 0))
    ttk.Label(header, text="RUNTIME CONNECTED", style="CouncilSummary.TLabel").pack(side="right")

    # Tkinter widgets and scheduling APIs are owned exclusively by its main
    # thread. Background runtime/model/registry work posts callbacks into this
    # queue; it must never directly call root.after or modify Tk variables.
    ui_callbacks: queue.Queue[Any] = queue.Queue()
    ui_lifetime: dict[str, Any] = {"closing": False, "pump_id": None}

    def post_ui(callback) -> None:
        if not ui_lifetime["closing"]:
            ui_callbacks.put(callback)

    def drain_ui_callbacks() -> None:
        if ui_lifetime["closing"]:
            return
        try:
            for _ in range(80):
                try:
                    callback = ui_callbacks.get_nowait()
                except queue.Empty:
                    break
                callback()
        finally:
            if not ui_lifetime["closing"]:
                ui_lifetime["pump_id"] = root.after(50, drain_ui_callbacks)

    session: Dict[str, Any] = {}
    cohorts: Dict[str, CohortWorkflow] = {}

    general = ttk.LabelFrame(root, text="Mission & authority", padding=10)
    general.pack(fill="x", padx=12, pady=(4, 8))

    fields: Dict[str, Any] = {
        "councilId": tk.StringVar(value="council-human-workflow-r1"),
        "missionId": tk.StringVar(value="m-human-workflow-r1"),
        "targetRoot": tk.StringVar(value=target_root or os.getcwd()),
        "maxConcurrent": tk.StringVar(value="1"),
        "contextBudget": tk.StringVar(value="128000"),
        "executionSeconds": tk.StringVar(value="1800"),
    }
    ttk.Label(general, text="Council ID").grid(row=0, column=0, sticky="w", padx=4, pady=4)
    ttk.Entry(general, textvariable=fields["councilId"]).grid(row=0, column=1, sticky="ew", padx=4, pady=4)
    ttk.Label(general, text="Mission ID").grid(row=0, column=2, sticky="w", padx=4, pady=4)
    ttk.Entry(general, textvariable=fields["missionId"]).grid(row=0, column=3, columnspan=3, sticky="ew", padx=4, pady=4)

    ttk.Label(general, text="Target root").grid(row=1, column=0, sticky="w", padx=4, pady=4)
    ttk.Entry(general, textvariable=fields["targetRoot"]).grid(row=1, column=1, columnspan=4, sticky="ew", padx=4, pady=4)
    def browse_target() -> None:
        selected = filedialog.askdirectory(initialdir=fields["targetRoot"].get() or os.getcwd())
        if selected:
            fields["targetRoot"].set(selected)
    ttk.Button(general, text="Browse…", command=browse_target).grid(row=1, column=5, sticky="ew", padx=4, pady=4)

    for col, (key, label) in enumerate((("maxConcurrent", "Concurrent cohorts"), ("contextBudget", "Context budget"), ("executionSeconds", "Execution seconds"))):
        base = col * 2
        ttk.Label(general, text=label).grid(row=2, column=base, sticky="w", padx=4, pady=4)
        ttk.Entry(general, textvariable=fields[key], width=18).grid(row=2, column=base + 1, sticky="ew", padx=4, pady=4)
    for col in (1, 3, 5):
        general.columnconfigure(col, weight=1)

    options = ttk.Frame(general)
    options.grid(row=3, column=0, columnspan=6, sticky="ew", pady=(6, 0))
    file_mut = tk.BooleanVar(value=True)
    shell = tk.BooleanVar(value=True)
    verify = tk.BooleanVar(value=True)
    ttk.Checkbutton(options, text="File mutation", variable=file_mut).pack(side="left", padx=6)
    ttk.Checkbutton(options, text="Shell", variable=shell).pack(side="left", padx=6)
    ttk.Checkbutton(options, text="Human verification", variable=verify).pack(side="left", padx=6)
    ttk.Label(options, text="Network").pack(side="left", padx=(18, 4))
    network = tk.StringVar(value="remote_allowed")
    ttk.Combobox(
        options, textvariable=network, state="readonly", width=18,
        values=("remote_allowed", "local_only", "denied"),
    ).pack(side="left")
    body = ttk.Panedwindow(root, orient="vertical")
    body.pack(fill="both", expand=True, padx=10, pady=(0, 8))

    cohort_frame = ttk.LabelFrame(body, text="Cohorts", padding=8)
    body.add(cohort_frame, weight=3)
    summary_var = tk.StringVar(value="No cohorts configured")
    ttk.Label(cohort_frame, textvariable=summary_var, style="CouncilSummary.TLabel").pack(fill="x", pady=(0, 6))
    card_canvas = tk.Canvas(cohort_frame, height=200, borderwidth=0, highlightthickness=0)
    card_scroll = ttk.Scrollbar(cohort_frame, orient="vertical", command=card_canvas.yview)
    card_canvas.configure(yscrollcommand=card_scroll.set)
    card_scroll.pack(side="right", fill="y")
    card_canvas.pack(fill="both", expand=True)
    card_list = ttk.Frame(card_canvas)
    card_window = card_canvas.create_window((0, 0), window=card_list, anchor="nw")
    card_list.bind("<Configure>", lambda _e: card_canvas.configure(scrollregion=card_canvas.bbox("all")))
    card_canvas.bind("<Configure>", lambda e: card_canvas.itemconfigure(card_window, width=e.width))
    selected_cohort = tk.StringVar(value="")

    editor = ttk.Frame(cohort_frame)
    editor.pack(fill="x", pady=(8, 0))
    evars = {
        "cohort": tk.StringVar(value="c01"),
        "provider": tk.StringVar(value="openrouter"),
        "model": tk.StringVar(value=""),
        "vessels": tk.StringVar(value="11"),
        "configuration": tk.StringVar(value="default"),
    }
    from capt_ui.operator.providers import ProviderManager
    from capt_ui.operator.council_ux import (
        approval_presentation, council_receipt_summary, draft_path,
        execution_summary, mission_execution_projection, existing_driver_run_conflicts,
        existing_council_receipt_conflict,
        load_draft_snapshot,
        provider_catalog, refresh_provider_models, save_draft_snapshot,
    )
    from capt_ui.operator.council_workflow import workflow_digest
    providers = ProviderManager()
    catalog = provider_catalog(providers)
    ttk.Label(editor, text="Cohort ID").grid(row=0, column=0, sticky="w")
    ttk.Entry(editor, textvariable=evars["cohort"], width=22).grid(row=0, column=1, sticky="ew")
    ttk.Label(editor, text="Provider").grid(row=0, column=2, sticky="w")
    ttk.Combobox(editor, textvariable=evars["provider"], width=19,
                 values=tuple(catalog)).grid(row=0, column=3, sticky="ew")
    ttk.Label(editor, text="Model").grid(row=0, column=4, sticky="w")
    model_combo = ttk.Combobox(editor, textvariable=evars["model"], width=30)
    model_combo.grid(row=0, column=5, sticky="ew")
    ttk.Label(editor, text="Vessels").grid(row=0, column=6, sticky="w")
    ttk.Entry(editor, textvariable=evars["vessels"], width=6).grid(row=0, column=7)
    ttk.Label(editor, text="Config").grid(row=0, column=8, sticky="w")
    ttk.Entry(editor, textvariable=evars["configuration"], width=10).grid(row=0, column=9)
    def update_models(*_args) -> None:
        model_combo.configure(values=catalog.get(evars["provider"].get().strip(), ()))
    evars["provider"].trace_add("write", update_models)
    def refresh_models() -> None:
        name = evars["provider"].get().strip()
        status_var.set("Refreshing registered models for " + name + "…")
        def worker() -> None:
            try:
                fresh = refresh_provider_models(providers, name)
            except Exception as exc:
                post_ui( lambda exc=exc: messagebox.showwarning("Model discovery", _friendly_error(exc)))
            else:
                def apply() -> None:
                    catalog[name] = fresh
                    update_models()
                    status_var.set(f"{len(fresh)} models discovered for {name}; choose or type a model ID.")
                post_ui( apply)
        threading.Thread(target=worker, daemon=True).start()
    ttk.Button(editor, text="Refresh models", command=refresh_models).grid(row=0, column=10)
    update_models()
    objective = tk.Text(editor, height=3, wrap="word", font=("SF Mono", 11), undo=True)
    ttk.Label(editor, text="Cohort objective").grid(row=1, column=0, sticky="nw", padx=3, pady=5)
    objective.grid(row=1, column=1, columnspan=9, sticky="ew", padx=3, pady=5)
    editor.columnconfigure(5, weight=1)

    approval_frame = ttk.LabelFrame(body, text="Governed approvals", padding=8)
    body.add(approval_frame, weight=2)
    approval_cols = ("cohort", "request", "state", "remaining", "expires")
    approval_wrap = ttk.Frame(approval_frame)
    approval_wrap.pack(fill="both", expand=True)
    approval_tree = ttk.Treeview(approval_wrap, columns=approval_cols, show="headings", height=5)
    for col, width in (("cohort", 150), ("request", 300), ("state", 110), ("remaining", 80), ("expires", 190)):
        approval_tree.heading(col, text=col.title())
        approval_tree.column(col, width=width, minwidth=70, anchor="w", stretch=(col == "request"))
    approval_y = ttk.Scrollbar(approval_wrap, orient="vertical", command=approval_tree.yview)
    approval_x = ttk.Scrollbar(approval_wrap, orient="horizontal", command=approval_tree.xview)
    approval_tree.configure(yscrollcommand=approval_y.set, xscrollcommand=approval_x.set)
    approval_tree.grid(row=0, column=0, sticky="nsew")
    approval_y.grid(row=0, column=1, sticky="ns")
    approval_x.grid(row=1, column=0, sticky="ew")
    approval_wrap.rowconfigure(0, weight=1)
    approval_wrap.columnconfigure(0, weight=1)

    approval_tree.tag_configure("pending", foreground="#D9B76D")
    approval_tree.tag_configure("approved", foreground="#5ABD97")
    approval_tree.tag_configure("error", foreground="#E78989")
    ttk.Label(approval_frame, text="Runtime execution receipts · unknown is not success",
              style="CouncilSub.TLabel").pack(fill="x", pady=(8, 3))
    lane_cols = ("cohort", "run", "state", "reconciliation", "diagnostic")
    lane_tree = ttk.Treeview(approval_frame, columns=lane_cols, show="headings", height=3)
    for col, size in (("cohort", 170), ("run", 360), ("state", 120), ("reconciliation", 130), ("diagnostic", 260)):
        lane_tree.heading(col, text=col.title())
        lane_tree.column(col, width=size, anchor="w", stretch=(col == "run"))
    lane_tree.pack(fill="x", pady=(0, 4))

    status_var = tk.StringVar(value="Configure a workflow. Requesting approval does not approve it.")
    status_bar = ttk.Frame(root, padding=(12, 5))
    status_bar.pack(side="bottom", fill="x")
    ttk.Label(status_bar, textvariable=status_var).pack(side="left", fill="x", expand=True)

    def select_cohort(cohort_id: str) -> None:
        if cohort_id not in cohorts:
            return
        selected_cohort.set(cohort_id)
        item = cohorts[cohort_id]
        evars["cohort"].set(item.cohort_id)
        evars["provider"].set(item.provider)
        evars["model"].set(item.model)
        evars["vessels"].set(str(item.vessels_per_cohort))
        evars["configuration"].set(item.configuration_id)
        objective.delete("1.0", "end")
        objective.insert("1.0", item.objective)

    def redraw_cohorts() -> None:
        for child in card_list.winfo_children():
            child.destroy()
        for ordinal, cohort in enumerate(cohorts.values(), 1):
            card = ttk.LabelFrame(card_list, text=f"{ordinal:02d} · {cohort.cohort_id}", padding=7)
            card.pack(fill="x", padx=5, pady=4)
            ttk.Label(card, text=f"{cohort.provider} / {cohort.model}", style="CouncilSummary.TLabel").pack(anchor="w")
            line = ttk.Frame(card)
            line.pack(fill="x")
            ttk.Label(line, text=f"{cohort.vessels_per_cohort} logical vessels · {cohort.configuration_id} · {cohort.objective[:115]}",
                      wraplength=920).pack(side="left", fill="x", expand=True, anchor="w")
            ttk.Button(line, text="Edit", command=lambda cid=cohort.cohort_id: select_cohort(cid)).pack(side="right", padx=6)
        logical = sum(item.vessels_per_cohort for item in cohorts.values())
        mode = "sequential" if fields["maxConcurrent"].get().strip() == "1" else "parallel-capable"
        summary_var.set(f"{len(cohorts)} cohorts · {logical} logical vessels · {mode} · one governed execution per cohort (multiple HTTP requests possible)")

    fields["maxConcurrent"].trace_add("write", lambda *_: redraw_cohorts())

    def upsert_cohort() -> None:
        try:
            item = CohortWorkflow(
                cohort_id=evars["cohort"].get().strip(),
                provider=evars["provider"].get().strip(),
                model=evars["model"].get().strip(),
                objective=objective.get("1.0", "end").strip(),
                vessels_per_cohort=int(evars["vessels"].get()),
                configuration_id=evars["configuration"].get().strip() or "default",
            ).validate()
        except Exception as exc:
            messagebox.showerror("Invalid cohort", _friendly_error(exc))
            return
        previous = selected_cohort.get()
        if previous and previous != item.cohort_id:
            cohorts.pop(previous, None)
        cohorts[item.cohort_id] = item
        selected_cohort.set(item.cohort_id)
        redraw_cohorts()
        schedule_autosave()

    def remove_cohort() -> None:
        cohort_id = selected_cohort.get()
        if cohort_id in cohorts:
            cohorts.pop(cohort_id)
            selected_cohort.set("")
        redraw_cohorts()
        schedule_autosave()

    buttons = ttk.Frame(cohort_frame)
    buttons.pack(fill="x", pady=(6, 0))
    ttk.Button(buttons, text="Add / update cohort", command=upsert_cohort).pack(side="left")
    ttk.Button(buttons, text="Remove selected", command=remove_cohort).pack(side="left", padx=6)

    def build_workflow() -> CouncilWorkflow:
        return CouncilWorkflow(
            council_id=fields["councilId"].get().strip(),
            mission_id=fields["missionId"].get().strip(),
            target_root=fields["targetRoot"].get().strip(),
            cohorts=tuple(cohorts.values()),
            max_concurrent_cohorts=int(fields["maxConcurrent"].get()),
            requested_context_budget=int(fields["contextBudget"].get()),
            requested_execution_seconds=int(fields["executionSeconds"].get()),
            file_mutation_allowed=file_mut.get(),
            shell_access_allowed=shell.get(),
            human_verification_required=verify.get(),
            provider_network_policy=network.get(),
        ).validate()

    def apply_workflow(workflow: CouncilWorkflow) -> None:
        fields["councilId"].set(workflow.council_id)
        fields["missionId"].set(workflow.mission_id)
        fields["targetRoot"].set(workflow.target_root)
        fields["maxConcurrent"].set(str(workflow.max_concurrent_cohorts))
        fields["contextBudget"].set(str(workflow.requested_context_budget))
        fields["executionSeconds"].set(str(workflow.requested_execution_seconds))
        file_mut.set(workflow.file_mutation_allowed)
        shell.set(workflow.shell_access_allowed)
        verify.set(workflow.human_verification_required)
        network.set(workflow.provider_network_policy)
        cohorts.clear()
        cohorts.update((c.cohort_id, c) for c in workflow.cohorts)
        redraw_cohorts()
        if cohorts:
            select_cohort(next(iter(cohorts)))
        schedule_autosave()

    def load_donor_template() -> None:
        try:
            apply_workflow(donor_convergence_workflow(fields["targetRoot"].get().strip()))
            status_var.set("Loaded exact donor template: 3 cohorts × 11 vessels, sequential.")
        except Exception as exc:
            messagebox.showerror("Template error", _friendly_error(exc))

    preset_var = tk.StringVar(value="Donor convergence (3 × 11)")
    ttk.Combobox(
        buttons, textvariable=preset_var, width=27, state="readonly",
        values=("Donor convergence (3 × 11)", "Blank Council", "Latest autosave"),
    ).pack(side="right", padx=(6, 0))

    def load_preset() -> None:
        choice = preset_var.get()
        if choice == "Donor convergence (3 × 11)":
            load_donor_template()
        elif choice == "Blank Council":
            apply_workflow(CouncilWorkflow(
                council_id="council-new", mission_id="m-new",
                target_root=fields["targetRoot"].get(),
                cohorts=(CohortWorkflow("cohort-1", "openrouter", "model-id",
                                        "Describe the mission objective.", 1),),
            ).validate())
            status_var.set("Blank Council prepared; edit and validate before requesting approvals.")
        elif choice == "Latest autosave":
            recover_autosave()
        schedule_autosave()
    ttk.Button(buttons, text="Load preset", command=load_preset).pack(side="right")

    draft = ttk.Frame(root)
    draft.pack(fill="x", padx=10, pady=(0, 6))

    autosave_file = draft_path()
    autosave_job: dict[str, Any] = {"id": None, "paused": True}

    def editor_snapshot() -> dict[str, str]:
        return {**{key: var.get() for key, var in evars.items()},
                "objective": objective.get("1.0", "end").strip()}

    def persist_autosave() -> None:
        autosave_job["id"] = None
        if autosave_job["paused"]:
            return
        try:
            # Keep even intermediate invalid edits as presentation-only metadata.
            # The canonical workflow portion contains the last parseable values.
            if autosave_file.exists():
                record = json.loads(autosave_file.read_text())
            else:
                record = {}
            try:
                record.update(build_workflow().to_record())
            except (ValueError, TypeError):
                if not record:
                    record = donor_convergence_workflow(str(Path.home())).to_record()
                record["cohorts"] = [c.to_record() for c in cohorts.values()] or record["cohorts"]
            record["selectedCohort"] = selected_cohort.get()
            record["editorDraft"] = editor_snapshot()
            record["pendingFields"] = {key: var.get() for key, var in fields.items()}
            save_draft_snapshot(record, autosave_file)
        except Exception as exc:
            status_var.set("Autosave unavailable: " + _friendly_error(exc))

    def schedule_autosave(*_args) -> None:
        if autosave_job["paused"]:
            return
        if autosave_job["id"] is not None:
            root.after_cancel(autosave_job["id"])
        autosave_job["id"] = root.after(650, persist_autosave)

    for var in (*fields.values(), *evars.values(), file_mut, shell, verify, network):
        var.trace_add("write", schedule_autosave)
    objective.bind("<KeyRelease>", schedule_autosave, add="+")

    def recover_autosave() -> None:
        if not autosave_file.exists():
            return
        try:
            prior = load_draft_snapshot(autosave_file)
        except Exception as exc:
            status_var.set("Autosaved draft could not be validated: " + str(exc))
            return
        if prior and messagebox.askyesno(
            "Recover Council draft",
            "A saved Council draft exists. Recover it? This does not restore or approve any execution.",
        ):
            record = json.loads(autosave_file.read_text())
            apply_workflow(prior)
            if isinstance(record.get("pendingFields"), dict):
                for key, value in record["pendingFields"].items():
                    if key in fields:
                        fields[key].set(str(value))
            target = str(record.get("selectedCohort") or "")
            if target in cohorts:
                select_cohort(target)
            editor_record = record.get("editorDraft") or {}
            if isinstance(editor_record, dict):
                for key in evars:
                    if key in editor_record:
                        evars[key].set(str(editor_record[key]))
                if "objective" in editor_record:
                    objective.delete("1.0", "end")
                    objective.insert("1.0", str(editor_record["objective"]))
            status_var.set("Draft recovered; approvals must be requested again.")

    def ensure_session_matches_current_draft() -> bool:
        if not session:
            messagebox.showwarning("No approval session", "Request approvals first.")
            return False
        try:
            current = build_workflow()
        except Exception as exc:
            messagebox.showerror("Invalid Council", _friendly_error(exc))
            return False
        if workflow_digest(current) != session.get("workflowDigest"):
            messagebox.showwarning(
                "Council configuration changed",
                "This draft differs from the approved workflow. Request fresh approvals for the new configuration.",
            )
            return False
        cohort_id = selected_cohort.get()
        if cohort_id in cohorts and editor_snapshot() != {
            "cohort": cohorts[cohort_id].cohort_id,
            "provider": cohorts[cohort_id].provider,
            "model": cohorts[cohort_id].model,
            "vessels": str(cohorts[cohort_id].vessels_per_cohort),
            "configuration": cohorts[cohort_id].configuration_id,
            "objective": cohorts[cohort_id].objective,
        }:
            messagebox.showwarning("Unapplied cohort edits", "Apply the cohort edits and request fresh approvals.")
            return False
        return True

    def save_draft() -> None:
        try:
            workflow = build_workflow()
        except Exception as exc:
            messagebox.showerror("Invalid workflow", _friendly_error(exc))
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json", filetypes=[("CAPT workflow", "*.json"), ("JSON", "*.json")]
        )
        if path:
            Path(path).write_text(json.dumps(workflow.to_record(), indent=2) + "\n")
            status_var.set("Draft saved: " + path)
    def load_draft() -> None:
        path = filedialog.askopenfilename(filetypes=[("CAPT workflow", "*.json"), ("JSON", "*.json")])
        if not path:
            return
        try:
            workflow = CouncilWorkflow.from_mapping(json.loads(Path(path).read_text())).validate()
            apply_workflow(workflow)
            status_var.set("Draft loaded: " + path)
        except Exception as exc:
            messagebox.showerror("Load failed", _friendly_error(exc))

    ttk.Button(draft, text="Save workflow draft", command=save_draft).pack(side="left")
    ttk.Button(draft, text="Load workflow draft", command=load_draft).pack(side="left", padx=6)

    def redraw_approvals(rows) -> None:
        for item in approval_tree.get_children():
            approval_tree.delete(item)
        for row in rows:
            label, kind = approval_presentation(row.get("state", ""))
            approval_tree.insert("", "end", iid=row["requestId"], tags=(kind,), values=(
                row.get("cohortId"), row.get("requestId"), label,
                row.get("remainingUses"), row.get("expiresAt"),
            ))

    lane_refresh = {"inflight": False, "closing": False}

    def refresh_execution_lanes() -> None:
        if lane_refresh["closing"] or lane_refresh["inflight"]:
            return
        # Reattach by exact workflow mission/task/run IDs even after the window
        # restarts. Never restore approvals or trigger a provider replay.
        try:
            workflow = CouncilWorkflow.from_mapping(session["workflow"]).validate() if session else build_workflow()
        except Exception:
            return
        lane_refresh["inflight"] = True
        def worker() -> None:
            from desktop.desktop_runtime_client import RuntimeClient
            reader = RuntimeClient(sock, token_file, connect_timeout=3.0, command_timeout=8.0)
            try:
                reader.connect()
                rows = mission_execution_projection(reader, workflow)
                summary, severity = execution_summary(rows)
            except Exception as exc:
                error_text = _friendly_error(exc)
                def unavailable() -> None:
                    lane_refresh["inflight"] = False
                    if not lane_refresh["closing"]:
                        status_var.set("Runtime status unavailable: " + error_text)
                post_ui( unavailable)
                return
            finally:
                reader.disconnect()
            def render() -> None:
                lane_refresh["inflight"] = False
                if lane_refresh["closing"]:
                    return
                for child in lane_tree.get_children():
                    lane_tree.delete(child)
                for item in rows:
                    lane_tree.insert("", "end", values=(
                        item["cohortId"], item["driverRunId"],
                        item["state"], item["reconciliation"], item.get("diagnostic", ""),
                    ))
                provenance = "" if session else "Historical mission IDs; current draft binding unverified. "
                if severity in ("error", "review"):
                    status_var.set(provenance + summary)
                elif not run_active["value"] and severity != "unknown":
                    status_var.set(provenance + summary)
            post_ui( render)
        threading.Thread(target=worker, daemon=True).start()

    def poll_receipts() -> None:
        if lane_refresh["closing"]:
            return
        refresh_execution_lanes()
        lane_refresh["poll_id"] = root.after(7000, poll_receipts)

    action_buttons: list[Any] = []
    run_active = {"value": False}

    def set_run_busy(busy: bool) -> None:
        run_active["value"] = busy
        for button in action_buttons:
            if busy:
                button.state(["disabled"])
            else:
                button.state(["!disabled"])

    def request_approvals() -> None:
        try:
            cohort_id = selected_cohort.get()
            if cohort_id in cohorts and editor_snapshot() != {
                "cohort": cohorts[cohort_id].cohort_id,
                "provider": cohorts[cohort_id].provider,
                "model": cohorts[cohort_id].model,
                "vessels": str(cohorts[cohort_id].vessels_per_cohort),
                "configuration": cohorts[cohort_id].configuration_id,
                "objective": cohorts[cohort_id].objective,
            }:
                messagebox.showwarning("Pending edits", "Apply cohort edits before requesting approvals.")
                return
            workflow = build_workflow()
        except Exception as exc:
            messagebox.showerror("Invalid Council", _friendly_error(exc))
            return
        set_run_busy(True)
        status_var.set("Requesting governed approvals; no execution dispatched.")
        def worker() -> None:
            try:
                conflicts = existing_driver_run_conflicts(op.client, workflow)
                council_conflict = existing_council_receipt_conflict(op.client, workflow)
                if conflicts or council_conflict:
                    detail = ", ".join(conflicts)
                    if council_conflict:
                        detail = (detail + "\n" if detail else "") + council_conflict
                    post_ui(lambda detail=detail: messagebox.showwarning(
                        "Durable execution identity already used",
                        "These identities are immutable and cannot be safely replayed:\n"
                        + detail + "\n\nFor a fresh execution, assign BOTH a new Council ID "
                        "and a new Mission ID, then request fresh approvals.",
                    ))
                    return
                prepared = op.request_council_workflow(workflow)
                rows = op.council_workflow_status(prepared)
                def completed() -> None:
                    nonlocal session
                    session = prepared
                    redraw_approvals(rows)
                    refresh_execution_lanes()
                    status_var.set(f"Approval requests created for {workflow.logical_vessels} logical vessels.")
                post_ui( completed)
            except Exception as exc:
                post_ui( lambda exc=exc: messagebox.showerror("Approval request failed", _friendly_error(exc)))
            finally:
                post_ui( lambda: set_run_busy(False))
        threading.Thread(target=worker, daemon=True).start()

    def refresh_approvals() -> None:
        if not session:
            refresh_execution_lanes()
            return
        current = session
        def worker() -> None:
            try:
                rows = op.council_workflow_status(current)
                post_ui( lambda: redraw_approvals(rows))
                post_ui( refresh_execution_lanes)
            except Exception as exc:
                post_ui( lambda exc=exc: messagebox.showerror("Refresh failed", _friendly_error(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def decide(decision: str) -> None:
        if not ensure_session_matches_current_draft():
            return
        label = "APPROVE" if decision == "approve" else "DENY"
        if not messagebox.askyesno(
            f"{label} Council workflow",
            f"{label} every currently requested cohort in this exact workflow?",
        ):
            return
        set_run_busy(True)
        def worker() -> None:
            try:
                op.decide_council_workflow(session, decision, "Human decision from Council Workflow Builder.")
                rows = op.council_workflow_status(session)
                post_ui( lambda: redraw_approvals(rows))
                post_ui( lambda: status_var.set(f"Human decision recorded: {decision}."))
            except Exception as exc:
                post_ui( lambda exc=exc: messagebox.showerror("Decision failed", _friendly_error(exc)))
            finally:
                post_ui( lambda: set_run_busy(False))
        threading.Thread(target=worker, daemon=True).start()

    def launch() -> None:
        if not ensure_session_matches_current_draft():
            return
        try:
            rows = op.council_workflow_status(session)
        except Exception as exc:
            messagebox.showerror("Status failed", _friendly_error(exc))
            return
        if any(row.get("state") != "approved" for row in rows):
            messagebox.showwarning("Not approved", "Every cohort must be explicitly approved before launch.")
            redraw_approvals(rows)
            return
        if not messagebox.askyesno(
            "Launch governed Council",
            "Launch this exact approved Council through RuntimeService now?",
        ):
            return
        set_run_busy(True)
        status_var.set("Council running… controls are locked while RuntimeService owns the provider exchange.")

        def worker() -> None:
            try:
                receipt = op.run_council_workflow(session)
                post_ui( lambda receipt=receipt: status_var.set(
                    council_receipt_summary(receipt)
                ))
                post_ui( refresh_execution_lanes)
            except Exception as exc:
                post_ui( lambda exc=exc: messagebox.showerror("Council run failed", _friendly_error(exc)))
            finally:
                post_ui( lambda: set_run_busy(False))
        threading.Thread(target=worker, daemon=True).start()
        refresh_execution_lanes()

    def reconnect_runtime() -> None:
        if run_active["value"]:
            return
        set_run_busy(True)
        status_var.set("Reconnecting to CAPT RuntimeService...")
        def worker() -> None:
            try:
                op.disconnect()
                identity = op.connect()
                post_ui(lambda: status_var.set(
                    "Runtime reconnected; ledger sequence " +
                    str(identity.get("headSequence", "?")) + "."
                ))
                post_ui(refresh_execution_lanes)
            except Exception as exc:
                post_ui(lambda exc=exc: messagebox.showerror(
                    "CAPT runtime unavailable", _friendly_error(exc)
                ))
            finally:
                post_ui(lambda: set_run_busy(False))
        threading.Thread(target=worker, daemon=True).start()

    controls = ttk.Frame(root, padding=(12, 6))
    controls.pack(side="bottom", fill="x")
    request_button = ttk.Button(controls, text="1 · Request approvals", command=request_approvals)
    approve_button = ttk.Button(controls, text="2 · Approve", command=lambda: decide("approve"))
    deny_button = ttk.Button(controls, text="Deny", command=lambda: decide("deny"))
    launch_button = ttk.Button(controls, text="3 · Launch Council", command=launch)
    refresh_button = ttk.Button(controls, text="Refresh", command=refresh_approvals)
    reconnect_button = ttk.Button(controls, text="Reconnect", command=reconnect_runtime)
    request_button.pack(side="left")
    approve_button.pack(side="left", padx=6)
    deny_button.pack(side="left")
    launch_button.pack(side="left", padx=18)
    refresh_button.pack(side="right")
    reconnect_button.pack(side="right", padx=6)
    action_buttons.extend((request_button, approve_button, deny_button, launch_button, refresh_button, reconnect_button))

    def close() -> None:
        if run_active["value"] and not messagebox.askyesno(
            "Detach from running Council",
            "CAPT may still be processing provider requests. Closing only detaches the UI; "
            "it does NOT cancel or replay any execution. Continue?",
        ):
            return
        ui_lifetime["closing"] = True
        if ui_lifetime["pump_id"] is not None:
            root.after_cancel(ui_lifetime["pump_id"])
        lane_refresh["closing"] = True
        if lane_refresh.get("poll_id") is not None:
            root.after_cancel(lane_refresh["poll_id"])
        if autosave_job["id"] is not None:
            root.after_cancel(autosave_job["id"])
        persist_autosave()
        try:
            op.disconnect()
        finally:
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", close)
    if target_root:
        try:
            apply_workflow(donor_convergence_workflow(target_root))
        except Exception as exc:
            status_var.set("Template unavailable: " + _friendly_error(exc))
    recover_autosave()
    autosave_job["paused"] = False
    ui_lifetime["pump_id"] = root.after(50, drain_ui_callbacks)
    root.after(1000, poll_receipts)
    root.mainloop()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CAPT human Council Workflow Builder")
    default_sock, default_token = _defaults()
    parser.add_argument("--sock", default=os.environ.get("CAPT_RUNTIME_SOCK", default_sock))
    parser.add_argument("--token-file", default=os.environ.get("CAPT_RUNTIME_TOKEN_FILE", default_token))
    parser.add_argument("--target-root", default="")
    parser.add_argument("--template", choices=("blank", "donor-convergence"), default="blank")
    parser.add_argument("--headless", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)
    target = args.target_root or os.getcwd()
    if args.headless:
        workflow = (
            donor_convergence_workflow(target)
            if args.template == "donor-convergence"
            else CouncilWorkflow(
                council_id="council-draft",
                mission_id="m-draft",
                target_root=target,
                cohorts=(CohortWorkflow("c01", "openrouter", "model", "Objective", 1),),
            ).validate()
        )
        print(render_headless(workflow))
        return 0
    run_window(args.sock, args.token_file, target if args.template == "donor-convergence" else "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
