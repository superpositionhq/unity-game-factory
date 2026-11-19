"""The creation replay's structure comparison of an audio mixer (tools/unity-replay/verify.py, mixer_id_view): the ids
Unity makes at random for a mixer's groups, effects, snapshots and parameters are compared by mapping, and nothing
else gets looser. Plain dumps as ReplayDump.cs writes them; no Unity.

    python -m unittest discover -s tools/tests -p "test_replay_verify.py" -v
"""
import collections, itertools, os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'unity-replay'))
import verify  # noqa: E402

MIXER = 'Assets/Audio/Game.mixer'
REF = 'asset:%s#' % MIXER


def ids(field, n):
    return {'%s.data[%d]' % (field, i): v for i, v in enumerate(n)}


def mixer(seed, values=None, exposed=('Master', 'Music')):
    """A mixer as a dump shows it: Master with Music under it, an Attenuation effect each, one snapshot. Every random id
    is drawn from seed, so two seeds are two builds of the same mixer. values: {group: volume in the snapshot}."""
    counter = itertools.count(seed * 1000 + 1)
    new = lambda: [next(counter) * 7919 % 4294967291 + 1 for _ in range(4)]
    groups = {g: {'id': new(), 'volume': new(), 'pitch': new()} for g in ('Master', 'Music')}
    effects = [{'id': new(), 'mix': new()} for _ in groups]
    snap = new()
    values = {'Master': -6.0, 'Music': -12.5} if values is None else values
    ctrl = {'m_EnableSuspend': True, 'm_MasterGroup': REF + 'AudioMixerGroupController:Master',
            'm_Snapshots.Array.size': 1, 'm_Snapshots.Array.data[0]': REF + 'AudioMixerSnapshotController:Snapshot',
            'm_ExposedParameters.Array.size': len(exposed)}
    for i, g in enumerate(exposed):
        ctrl['m_ExposedParameters.Array.data[%d].name' % i] = g + 'Volume'
        ctrl.update(ids('m_ExposedParameters.Array.data[%d].guid' % i, groups[g]['volume']))
    objs = [{'type': 'UnityEditor.Audio.AudioMixerController', 'name': 'Game', 'main': True, 'props': ctrl}]
    for e in effects:
        p = {'m_EffectName': 'Attenuation', 'm_Bypass': False, 'm_Parameters.Array.size': 0}
        p.update(ids('m_EffectID', e['id']))
        p.update(ids('m_MixLevel', e['mix']))
        objs.append({'type': 'UnityEditor.Audio.AudioMixerEffectController', 'name': 'Attenuation', 'main': False, 'props': p})
    for g, x in groups.items():
        p = {'m_AudioMixer': REF[:-1], 'm_Mute': False, 'm_Effects.Array.size': 1,
             'm_Effects.Array.data[0]': REF + 'AudioMixerEffectController:Attenuation'}
        p.update(ids('m_GroupID', x['id']))
        p.update(ids('m_Volume', x['volume']))
        p.update(ids('m_Pitch', x['pitch']))
        p.update(ids('m_Send', [0, 0, 0, 0]))
        objs.append({'type': 'UnityEditor.Audio.AudioMixerGroupController', 'name': g, 'main': False, 'props': p})
    # the snapshot's values, a map keyed by parameter id (Unity keeps it sorted by id, so its order is random too)
    entries = sorted((groups[g]['volume'], v) for g, v in values.items())
    p = {'m_AudioMixer': REF[:-1], 'm_FloatValues.Array.size': len(entries), 'm_TransitionOverrides.Array.size': 0}
    p.update(ids('m_SnapshotID', snap))
    for i, (key, v) in enumerate(entries):
        p.update(ids('m_FloatValues.Array.data[%d].first' % i, key))
        p['m_FloatValues.Array.data[%d].second' % i] = v
    objs.append({'type': 'UnityEditor.Audio.AudioMixerSnapshotController', 'name': 'Snapshot', 'main': False, 'props': p})
    return {'path': MIXER, 'type': 'UnityEditor.Audio.AudioMixerController', 'importer': 'UnityEditor.AssetImporter',
            'importer_settings': {'m_MainObjectFileID': 24100000}, 'objects': objs}


def obj(asset, name):
    return next(o for o in asset['objects'] if o['name'] == name)


def group_ids(asset, group, field):
    p = obj(asset, group)['props']
    return [p['%s.data[%d]' % (field, i)] for i in range(4)]


def compare(rep, tru):
    counts = collections.Counter()
    res = verify.verify_assets({'assets': [rep]}, {'assets': [tru]}, counts)
    return res, counts


class MixerIds(unittest.TestCase):
    def test_two_builds_of_the_same_mixer_are_the_same(self):
        truth, replay = mixer(1), mixer(2)
        self.assertNotEqual(group_ids(truth, 'Master', 'm_GroupID'), group_ids(replay, 'Master', 'm_GroupID'))
        before = verify.diff_keys(verify.asset_view(replay), verify.asset_view(truth))
        self.assertTrue(any('m_GroupID' in k for k in before), before)
        res, counts = compare(replay, truth)
        self.assertEqual(res['diffs'], [])
        self.assertEqual(res['total'], {'same': 1})
        # 2 groups x (group, volume, pitch) + 2 effects x (effect, mix level) + the snapshot; the zero send stays
        self.assertEqual(counts['id_numbers'], 11)
        self.assertEqual(res['id_numbers'], ['%s: 11 ids' % MIXER])

    def test_the_same_ids_count_nothing(self):
        res, counts = compare(mixer(1), mixer(1))
        self.assertEqual(res['diffs'], [])
        self.assertEqual(counts['id_numbers'], 0)

    def test_a_changed_value_fails(self):
        res, _ = compare(mixer(2, values={'Master': -6.0, 'Music': -3.0}), mixer(1))
        self.assertEqual(res['total'].get('differs'), 1)
        self.assertTrue(any('m_FloatValues' in k and k.endswith('.second') for k in res['diffs'][0]['keys']), res['diffs'])
        replay = mixer(2)
        obj(replay, 'Music')['props']['m_Mute'] = True
        res, _ = compare(replay, mixer(1))
        self.assertEqual(res['diffs'][0]['keys'], ['objects[4].props.m_Mute'])

    def test_a_value_kept_for_another_parameter_fails(self):
        # the replay's snapshot holds -6 for Music and -12.5 for Master: the same numbers, wired the other way
        replay = mixer(2)
        p = obj(replay, 'Snapshot')['props']
        a, b = ([p['m_FloatValues.Array.data[%d].second' % i] for i in range(2)])
        p['m_FloatValues.Array.data[0].second'], p['m_FloatValues.Array.data[1].second'] = b, a
        res, _ = compare(replay, mixer(1))
        self.assertEqual(res['total'].get('differs'), 1)

    def test_an_exposed_parameter_wired_to_another_group_fails(self):
        res, _ = compare(mixer(2, exposed=('Master', 'Master')), mixer(1, exposed=('Master', 'Music')))
        self.assertEqual(res['total'].get('differs'), 1)
        self.assertIn('objects[0].props.m_ExposedParameters.Array.data[1].guid', res['diffs'][0]['keys'])

    def test_a_reference_to_an_id_no_object_defines_fails(self):
        replay = mixer(2)
        obj(replay, 'Game')['props'].update(ids('m_ExposedParameters.Array.data[0].guid', [5, 6, 7, 8]))
        res, _ = compare(replay, mixer(1))
        self.assertEqual(res['total'].get('differs'), 1)

    def test_one_id_paired_two_ways_fails(self):
        # the replay's two groups share one id: the truth's two ids cannot both map onto it
        replay = mixer(2)
        obj(replay, 'Music')['props'].update(ids('m_GroupID', group_ids(replay, 'Master', 'm_GroupID')))
        res, _ = compare(replay, mixer(1))
        self.assertEqual(res['total'].get('differs'), 1)
        self.assertTrue(any('m_GroupID' in k for k in res['diffs'][0]['keys']), res['diffs'])

    def test_a_missing_effect_fails(self):
        replay = mixer(2)
        replay['objects'] = [o for i, o in enumerate(replay['objects']) if i != 2]
        res, _ = compare(replay, mixer(1))
        self.assertEqual(res['total'].get('differs'), 1)

    def test_an_effect_of_another_kind_fails(self):
        replay = mixer(2)
        replay['objects'][1]['props']['m_EffectName'] = 'Lowpass Simple'
        res, _ = compare(replay, mixer(1))
        self.assertEqual(res['diffs'][0]['keys'], ['objects[1].props.m_EffectName'])

    def test_a_send_set_on_one_side_only_fails(self):
        replay = mixer(2)
        obj(replay, 'Music')['props'].update(ids('m_Send', group_ids(replay, 'Master', 'm_Volume')))
        res, _ = compare(replay, mixer(1))
        self.assertEqual(res['total'].get('differs'), 1)

    def test_four_numbers_outside_a_mixer_are_compared_as_numbers(self):
        def asset(n):
            return {'path': 'Assets/Data/Table.asset', 'type': 'Game.Table', 'importer': 'UnityEditor.AssetImporter',
                    'objects': [{'type': 'Game.Table', 'name': 'Table', 'main': True, 'props': ids('m_GroupID', n)}]}
        res, counts = compare(asset([9, 8, 7, 6]), asset([1, 2, 3, 4]))
        self.assertEqual(res['total'].get('differs'), 1)
        self.assertEqual(counts['id_numbers'], 0)

    def test_the_verdict_lists_the_exclusion(self):
        res, counts = compare(mixer(2), mixer(1))

        class Ctx:
            cfg = {}
        report = {'files': {'other': {'identical': 1}, 'assets': {}, 'missing': [], 'differs': [], 'extra': []},
                  'assets': res, 'scenes': {}, 'windows': [], 'rows': {}}
        v = verify.verdict(report, Ctx(), counts)
        self.assertTrue(v['pass'])
        ex = next(e for e in v['exclusions'] if e['id'] == 'id_numbers')
        self.assertEqual((ex['count'], ex['items']), (11, ['%s: 11 ids' % MIXER]))


if __name__ == '__main__':
    unittest.main()
