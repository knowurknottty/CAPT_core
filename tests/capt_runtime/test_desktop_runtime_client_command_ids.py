from desktop.desktop_runtime_client import RuntimeClient


def _client_and_messages():
    client = RuntimeClient('/tmp/unused.sock', '/tmp/unused.token')
    client.operator_id = 'operator-test'
    client.session_id = 'session-test'
    client._sock = object()
    messages = []
    client._send = lambda _sock, payload: messages.append(payload)
    client._recv = lambda _sock: {'status': 'accepted'}
    return client, messages


def test_new_idempotency_key_gets_new_command_id_for_same_operation_and_payload():
    client, messages = _client_and_messages()
    payload = {'originalPrompt': 'same prompt', 'model': 'tencent/hy3'}

    client.command('compile_prompt_proposal', payload, 'retry-a')
    client.command('compile_prompt_proposal', payload, 'retry-b')

    first = messages[0]['command']
    second = messages[1]['command']
    assert first['idempotencyKey'] == 'retry-a'
    assert second['idempotencyKey'] == 'retry-b'
    assert first['commandId'] != second['commandId']


def test_same_explicit_idempotency_key_keeps_same_command_id():
    client, messages = _client_and_messages()
    payload = {'originalPrompt': 'same prompt', 'model': 'tencent/hy3'}

    client.command('compile_prompt_proposal', payload, 'same-replay-key')
    client.command('compile_prompt_proposal', payload, 'same-replay-key')

    assert messages[0]['command']['commandId'] == messages[1]['command']['commandId']
