"""The creation replay's ledger (tools/unity-replay/ledger.py, as_claude): Antigravity's rows read as Claude Code's
where their effect is known, and every other row left as it is. No Unity.

    python -m unittest discover -s tools/tests -p "test_replay_ledger.py" -v
"""
import os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'unity-replay'))
import ledger  # noqa: E402


def row(tool, inp, agent='antigravity'):
    return {'agent': agent, 'event': 'PostToolUse', 'tool': tool, 'input': inp, 'time': '2026-11-20T10:00:00.000+00:00'}


class AsClaude(unittest.TestCase):
    def test_run_command_is_a_bash_command(self):
        a = ledger.as_claude(row('run_command', {'CommandLine': 'unity-heavy.ps1 -Step Build', 'Cwd': 'C:/UnityWork'}))
        self.assertEqual(a['tool'], 'Bash')
        self.assertEqual(a['input']['command'], 'unity-heavy.ps1 -Step Build')
        self.assertEqual(a['input']['Cwd'], 'C:/UnityWork', 'the other arguments stay')

    def test_write_file_is_a_write_and_edit_file_an_edit(self):
        w = ledger.as_claude(row('write_file', {'Path': 'C:/UnityWork/games/g/Assets/A.cs', 'Content': 'class A {}\n'}))
        self.assertEqual((w['tool'], w['input']), ('Write', {'file_path': 'C:/UnityWork/games/g/Assets/A.cs',
                                                            'content': 'class A {}\n'}))
        e = ledger.as_claude(row('edit_file', {'Path': 'C:/UnityWork/games/g/Assets/A.cs', 'Target': 'A',
                                               'Replacement': 'B', 'AllowMultiple': True}))
        self.assertEqual((e['tool'], e['input']), ('Edit', {'file_path': 'C:/UnityWork/games/g/Assets/A.cs',
                                                           'old_string': 'A', 'new_string': 'B', 'replace_all': True}))

    def test_an_append_is_an_append(self):
        a = ledger.as_claude(row('write_file', {'Path': 'C:/UnityWork/games/g/a.txt', 'Content': 'more', 'Append': True}))
        self.assertEqual((a['tool'], a['input']), ('Append', {'file_path': 'C:/UnityWork/games/g/a.txt', 'content': 'more'}))

    def test_another_file_tool_leaves_the_file_unknown(self):
        r = ledger.as_claude(row('replace_file_content', {'TargetFile': 'C:/UnityWork/games/g/Assets/B.cs',
                                                          'ReplacementChunks': []}))
        self.assertEqual((r['tool'], r['input']['file_path'], r['input']['tool']),
                         ('Unreplayed', 'C:/UnityWork/games/g/Assets/B.cs', 'replace_file_content'))

    def test_reads_and_other_agents_rows_are_unchanged(self):
        for a in (row('read_file', {'Path': 'C:/UnityWork/games/g/a.txt'}),
                  row('run_command', {'CommandLine': 'dir'}, 'codex'),
                  row('Write', {'file_path': 'x', 'content': 'y'}, 'claude')):
            self.assertIs(ledger.as_claude(a), a)


if __name__ == '__main__':
    unittest.main()
