"""Human-facing Council Workflow Builder.

The UI configures exact cohort geometry and provider/model assignments, then
uses the shared Operator facade for governed approval and execution. It never
mints authority locally and never auto-approves.
"""
from __future__ import annotations

import argparse
import json
import os
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
    root.title("CAPT · Model Council")
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
        text="  Human-configured cohorts · governed approval · one provider call per cohort",
        style="CouncilSub.TLabel",
    ).pack(side="left", padx=(8, 0))
    ttk.Label(header, text="RUNTIME CONNECTED", style="CouncilSummary.TLabel").pack(side="right")

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
    columns = ("cohort", "provider", "model", "vessels", "configuration")
    tree_wrap = ttk.Frame(cohort_frame)
    tree_wrap.pack(fill="both", expand=True)
    cohort_tree = ttk.Treeview(tree_wrap, columns=columns, show="headings", height=7, selectmode="browse")
    widths = {"cohort": 150, "provider": 130, "model": 330, "vessels": 80, "configuration": 140}
    for col in columns:
        cohort_tree.heading(col, text=col.title())
        cohort_tree.column(col, width=widths[col], minwidth=70, anchor="w", stretch=(col == "model"))
    cohort_y = ttk.Scrollbar(tree_wrap, orient="vertical", command=cohort_tree.yview)
    cohort_x = ttk.Scrollbar(tree_wrap, orient="horizontal", command=cohort_tree.xview)
    cohort_tree.configure(yscrollcommand=cohort_y.set, xscrollcommand=cohort_x.set)
    cohort_tree.grid(row=0, column=0, sticky="nsew")
    cohort_y.grid(row=0, column=1, sticky="ns")
    cohort_x.grid(row=1, column=0, sticky="ew")
    tree_wrap.rowconfigure(0, weight=1)
    tree_wrap.columnconfigure(0, weight=1)

    editor = ttk.Frame(cohort_frame)
    editor.pack(fill="x", pady=(8, 0))
    evars = {
        "cohort": tk.StringVar(value="c01"),
        "provider": tk.StringVar(value="openrouter"),
        "model": tk.StringVar(value=""),
        "vessels": tk.StringVar(value="11"),
        "configuration": tk.StringVar(value="default"),
    }
    for idx, (key, label) in enumerate((
        ("cohort", "Cohort"), ("provider", "Provider"), ("model", "Model"),
        ("vessels", "Vessels"), ("configuration", "Configuration"),
    )):
        ttk.Label(editor, text=label).grid(row=0, column=idx * 2, sticky="w", padx=3)
        ttk.Entry(editor, textvariable=evars[key], width=22).grid(
            row=0, column=idx * 2 + 1, sticky="ew", padx=3
        )
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

    status_var = tk.StringVar(value="Configure a workflow. Requesting approval does not approve it.")
    status_bar = ttk.Frame(root, padding=(12, 5))
    status_bar.pack(side="bottom", fill="x")
    ttk.Label(status_bar, textvariable=status_var).pack(side="left", fill="x", expand=True)

    def redraw_cohorts() -> None:
        for item in cohort_tree.get_children():
            cohort_tree.delete(item)
        for cohort in cohorts.values():
            cohort_tree.insert("", "end", iid=cohort.cohort_id, values=(
                cohort.cohort_id, cohort.provider, cohort.model,
                cohort.vessels_per_cohort, cohort.configuration_id,
            ))
        logical = sum(item.vessels_per_cohort for item in cohorts.values())
        mode = "sequential" if fields["maxConcurrent"].get().strip() == "1" else "parallel-capable"
        summary_var.set(
            f"{len(cohorts)} cohort{'s' if len(cohorts) != 1 else ''}  •  "
            f"{logical} logical vessels  •  {mode}  •  one provider call per cohort"
        )

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
        cohorts[item.cohort_id] = item
        redraw_cohorts()

    def remove_cohort() -> None:
        for item in cohort_tree.selection():
            cohorts.pop(str(item), None)
        redraw_cohorts()

    def load_selected(_event=None) -> None:
        selected = cohort_tree.selection()
        if not selected:
            return
        item = cohorts[str(selected[0])]
        evars["cohort"].set(item.cohort_id)
        evars["provider"].set(item.provider)
        evars["model"].set(item.model)
        evars["vessels"].set(str(item.vessels_per_cohort))
        evars["configuration"].set(item.configuration_id)
        objective.delete("1.0", "end")
        objective.insert("1.0", item.objective)

    cohort_tree.bind("<<TreeviewSelect>>", load_selected)
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

    def load_donor_template() -> None:
        try:
            apply_workflow(donor_convergence_workflow(fields["targetRoot"].get().strip()))
            status_var.set("Loaded exact donor template: 3 cohorts × 11 vessels, sequential.")
        except Exception as exc:
            messagebox.showerror("Template error", _friendly_error(exc))

    ttk.Button(buttons, text="Load donor 3×11 template", command=load_donor_template).pack(side="right")

    draft = ttk.Frame(root)
    draft.pack(fill="x", padx=10, pady=(0, 6))

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
            approval_tree.insert("", "end", iid=row["requestId"], values=(
                row.get("cohortId"), row.get("requestId"), row.get("state"),
                row.get("remainingUses"), row.get("expiresAt"),
            ))

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
        nonlocal session
        try:
            workflow = build_workflow()
            session = op.request_council_workflow(workflow)
            rows = op.council_workflow_status(session)
            redraw_approvals(rows)
            status_var.set(
                "Approval requests created. Human decision required before launch. "
                f"logical vessels={workflow.logical_vessels}"
            )
        except Exception as exc:
            messagebox.showerror("Approval request failed", _friendly_error(exc))

    def refresh_approvals() -> None:
        if not session:
            return
        try:
            redraw_approvals(op.council_workflow_status(session))
        except Exception as exc:
            messagebox.showerror("Refresh failed", _friendly_error(exc))

    def decide(decision: str) -> None:
        if not session:
            messagebox.showwarning("No session", "Request approvals first.")
            return
        label = "APPROVE" if decision == "approve" else "DENY"
        if not messagebox.askyesno(
            f"{label} Council workflow",
            f"{label} every currently requested cohort in this exact workflow?",
        ):
            return
        try:
            op.decide_council_workflow(session, decision, "Human decision from Council Workflow Builder.")
            refresh_approvals()
            status_var.set(f"Human decision recorded: {decision}.")
        except Exception as exc:
            messagebox.showerror("Decision failed", _friendly_error(exc))
    def launch() -> None:
        if not session:
            messagebox.showwarning("No session", "Request approvals first.")
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
                root.after(0, lambda: status_var.set(
                    "Council finished: " + json.dumps(receipt.get("result") or {}, sort_keys=True)[:900]
                ))
            except Exception as exc:
                root.after(0, lambda exc=exc: messagebox.showerror("Council run failed", _friendly_error(exc)))
            finally:
                root.after(0, lambda: set_run_busy(False))
        threading.Thread(target=worker, daemon=True).start()

    controls = ttk.Frame(root, padding=(12, 6))
    controls.pack(side="bottom", fill="x")
    request_button = ttk.Button(controls, text="1 · Request approvals", command=request_approvals)
    approve_button = ttk.Button(controls, text="2 · Approve", command=lambda: decide("approve"))
    deny_button = ttk.Button(controls, text="Deny", command=lambda: decide("deny"))
    launch_button = ttk.Button(controls, text="3 · Launch Council", command=launch)
    refresh_button = ttk.Button(controls, text="Refresh", command=refresh_approvals)
    request_button.pack(side="left")
    approve_button.pack(side="left", padx=6)
    deny_button.pack(side="left")
    launch_button.pack(side="left", padx=18)
    refresh_button.pack(side="right")
    action_buttons.extend((request_button, approve_button, deny_button, launch_button, refresh_button))

    def close() -> None:
        try:
            op.disconnect()
        finally:
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", close)
    if target_root:
        try:
            apply_workflow(donor_convergence_workflow(target_root))
        except Exception:
            pass
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
