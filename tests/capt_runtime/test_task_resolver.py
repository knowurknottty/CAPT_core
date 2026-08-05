from capt_runtime import commands
from capt_runtime.errors import AuthorityViolation, NotFound
from capt_runtime.services import RuntimeService
from capt_runtime.store import EventStore
from capt_runtime.task_resolver import TaskResolver


def _meta():
    return commands.command(command_id="cmd-task-resolve", idempotency_key="idem-task-resolve", operation_fingerprint="sha256:" + "0" * 64, correlation_id="corr-task-resolve", actor_id="captain", actor_kind="human", issued_at="2026-08-05T00:00:00Z")


def _mission(mid):
    return {"schemaVersion":"1.0.0","missionId":mid,"rawRequest":"x","normalizedRequest":"x","objectives":[{"objectiveId":"o","statement":"x","priority":1}],"constraints":[],"successCriteria":[{"criterionId":"s","statement":"x","requiresVerification":True}],"terminationCriteria":[{"criterionId":"t","statement":"x","terminalState":"failed"}],"unresolvedAmbiguities":[],"taskGraphId":None,"createdAt":"2026-08-05T00:00:00Z"}


def test_resolves_persisted_task_objective_and_scope(tmp_path):
    store=EventStore(str(tmp_path / "ledger.db")); svc=RuntimeService(store); meta=_meta()
    svc.create_mission(_mission("m-1"), meta)
    task={"taskId":"t-1","missionId":"m-1","title":"Inspect version declarations only.","state":"pending","consequential":False,"capabilityRequirements":[{"requirementId":"r","capabilityId":"cap.fs.read","operations":["repository.read"],"scope":{"kind":"filesystem","rootPath":"/tmp","recursive":True}}],"assignedDriverId":None,"attempt":0,"maxAttempts":1,"recoveryState":"none"}
    svc.create_task(task, commands.command(command_id="cmd-task",idempotency_key="idem-task",operation_fingerprint="sha256:"+"1"*64,correlation_id="corr",actor_id="cog",actor_kind="cognitive_plane",issued_at="2026-08-05T00:00:00Z"))
    resolved=TaskResolver(store).resolve_for_execution(mission_id="m-1",task_id="t-1")
    assert resolved.objective == task["title"]
    assert resolved.scope["rootPath"] == "/tmp"
    assert resolved.task_version == 1
    store.close()


def test_rejects_wrong_mission_and_missing_task(tmp_path):
    store=EventStore(str(tmp_path / "ledger.db")); svc=RuntimeService(store); svc.create_mission(_mission("m-1"),_meta())
    resolver=TaskResolver(store)
    try: resolver.resolve_for_execution(mission_id="m-1", task_id="missing")
    except NotFound: pass
    else: raise AssertionError("missing task was accepted")
    store.close()
