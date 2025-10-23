import sys, traceback, os
print('CWD:', os.getcwd())
print('sys.path:')
for p in sys.path:
    print(' -', p)
try:
    import mcp2_server
    print('Imported mcp2_server OK')
except Exception:
    traceback.print_exc()
