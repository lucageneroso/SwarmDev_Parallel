import json
from graph.aci import safe_cli_invoke, _resolve_cli_binary, CHROMADB_COLLECTION

cli = _resolve_cli_binary('cli-anything-chromadb')
res = safe_cli_invoke([
    cli, '--json', 'document', 'add',
    '--collection', CHROMADB_COLLECTION,
    '--document', 'test doc',
    '--id', 'doc1',
    '--metadata', '{"test":"1"}'
])
print("RESULT:", res)
