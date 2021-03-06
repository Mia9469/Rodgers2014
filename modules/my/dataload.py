"""Methods for loading data from my LBPB experiments

This is all specific to the layout of the data on my computer and
the typical defaults for this expt.
"""

import numpy as np
import pandas, kkpandas, kkpandas.kkrs
import os.path
from lxml import etree
from ns5_process import LBPB, RecordingSession
import itertools

# Convenience loading functions
def ulabel2spikes(ulabel, sort_spikes=True):
    """Return all spike times for specified ulabel"""
    # Load data
    gets = getstarted()

    # Parse ulabel
    session_name = kkpandas.kkrs.ulabel2session_name(ulabel)
    unum = kkpandas.kkrs.ulabel2unum(ulabel)

    # Get server
    kks = session2kk_server(session_name)

    # Load and sort
    spikes = np.asarray(kks.get(session=session_name, unit=unum).time)
    if sort_spikes:
        spikes = np.sort(spikes)
    
    return spikes

def ulabel2trials_info(ulabel):
    session_name = kkpandas.kkrs.ulabel2session_name(ulabel)
    rs = session2rs(session_name)
    trials_info = kkpandas.io.load_trials_info(rs.full_path)
    return trials_info

class SpikeServer:
    """Wrapper around ulabel2spikes to make it work like `pipeline` likes"""
    @classmethod
    def get(self, **kwargs):
        return ulabel2spikes(**kwargs)

def ulabel2dfolded(ulabel, trials_info=None, folding_kwargs=None, 
    time_picker=None, time_picker_kwargs=None,
    trial_picker_kwargs='random hits',
    old_behavior=False):
    """Convenience function for getting dict of folded from RS/kkpandas
    
    
    trial_picker_kwargs:
        Some reasonable defaults for kwargs ... see code  
    
    old_behavior : if True, use pipeline_over_block_oneevent
        if False, use the newer `pipeline`
    
    locking_event : what to lock to
        Only works for new behavior
    
    Returns: dict, picked trials label to Folded object
    """
    # Default kwargs for the pipeline
    # How to parse out trials
    if trial_picker_kwargs == 'random hits':
        trial_picker_kwargs = {
            'labels': LBPB.mixed_stimnames,
            'label_kwargs': [{'stim_name':s} for s in LBPB.mixed_stimnames],
            'nonrandom' : 0,
            'outcome' : 'hit'
            }
    elif trial_picker_kwargs == 'all':
        trial_picker_kwargs = {
            'labels': LBPB.stimnames, 
            'label_kwargs': [{'stim_name':s} for s in LBPB.stimnames],
            }
    elif trial_picker_kwargs == 'by outcome':
        # Generate labels for each combination of stimulus name and outcome
        labels = []
        label_kwargs = []
        for sname in LBPB.mixed_stimnames:
            for outcome in ['hit', 'error', 'wrong_port']:
                labels.append(sname + '-' + outcome)
                label_kwargs.append({'stim_name': sname, 'outcome': outcome})
        #~ label_kwargs = pandas.MultiIndex.from_tuples(
            #~ names=['stim_name', 'outcome'],
            #~ tuples=list(itertools.product(
                #~ LBPB.mixed_stimnames, ['hit', 'error', 'wrong_port'])))
        #~ labels = ['-'.join(t) for t in label_kwargs]
        trial_picker_kwargs = {'labels': labels, 'label_kwargs': label_kwargs,
            'nonrandom' : 0}
    elif trial_picker_kwargs == 'random hits by block':
        trial_picker_kwargs = {
            'labels': ['LB', 'PB'],
            'label_kwargs': [{'block': 2} , {'block': 4}],
            'nonrandom' : 0,
            'outcome' : 'hit'
            }

    # How to fold the window around each trial
    if folding_kwargs is None:
        folding_kwargs = {'dstart': -.25, 'dstop': .3}    


    # Load data
    gets = getstarted()
    
    
    if not old_behavior:
        if trials_info is None:
            trials_info = ulabel2trials_info(ulabel)

        if time_picker is None:
            time_picker = kkpandas.timepickers.TrialsInfoTimePicker(trials_info)
        if time_picker_kwargs is None:
            time_picker_kwargs = {'event_name': 'stim_onset'}
        
        res = kkpandas.pipeline.pipeline(trials_info,
            spike_server=SpikeServer,
            spike_server_kwargs={'ulabel': ulabel, 'sort_spikes': True},
            time_picker=time_picker,
            time_picker_kwargs=time_picker_kwargs,
            trial_picker_kwargs=trial_picker_kwargs,
            folding_kwargs=folding_kwargs,
            )
    
    else:
        # Parse ulabel
        session_name = kkpandas.kkrs.ulabel2session_name(ulabel)
        unum = kkpandas.kkrs.ulabel2unum(ulabel)

        # link back
        rs, kks = session2rs(session_name), session2kk_server(session_name)

        # Run the pipeline
        res = kkpandas.pipeline.pipeline_overblock_oneevent(
            kks, session_name, unum, rs,
            trial_picker_kwargs=trial_picker_kwargs,
            folding_kwargs=folding_kwargs)

    return res



def getstarted():
    """Load all my data into kkpandas and RS objects
    
    Returns: dict with following items:
        xmlfiles : dict, ratname to xml file
        kksfiles : dict, ratname to kk_server file
        kk_servers : dict, ratname to kk_server object
        xml_roots : dict, ratname to XML root object
        data_dirs : dict, ratname to location of data
        manual_units : dict, ratname to manually sorted units (XML objects)
            Includes only units from XML files with score above 3 and
            with session marked analyze=True
        unit_db : pandas DataFrame consisting of information about each ulabel
        session_db : pandas DataFrame of information about each session
        session_list : list of session names with analyze=True
    """
    # Get to the root directory of data.zip
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    if not os.path.exists(os.path.join(root_dir, 'metadata')):
        raise ValueError("Cannot find data in expected location")
    
    # Fill up res with hooks to data
    res = {}
    
    # Linking rat name to rat num
    res['ratname2num'] = pandas.Series(
        ['Rat 1', 'Rat 2', 'Rat 3', 'Rat 4', 'Rat 5', 'Rat 6'],
        ['CR12B', 'CR17B', 'YT6A', 'CR20B', 'CR21A', 'CR24A'])
    
    # Metadata: location of kk_servers
    res['kksfiles'] = dict([
        (ratname, os.path.join(root_dir, 'metadata', ratname + '_behaving.kks'))
        for ratname in res['ratname2num'].index])
    res['kk_servers'] = dict([
        (ratname, kkpandas.kkio.KK_Server.from_saved(kksfile))
        for ratname, kksfile in res['kksfiles'].items()])
    
    # Fix the relative paths in the kk_servers
    for ratname, kks in res['kk_servers'].items():
        for session_name in kks.session_d:
            kks.session_d[session_name] = os.path.join(
                root_dir, 'data', ratname, session_name, 'klusters0')

    # Data directory
    res['data_dirs'] = dict([(ratname, os.path.join(root_dir, 'data', ratname))
        for ratname in res['kksfiles'].keys()])
    
    # Metadata: unit_db and session_db
    res['unit_db'] = pandas.DataFrame.from_csv(
        os.path.join(root_dir, 'metadata', 'unit_db.csv'))
    res['session_db'] = pandas.DataFrame.from_csv(
        os.path.join(root_dir, 'metadata', 'sessions_df.csv'))    
    
    # For backwards compatibility: analyze should be str
    res['session_db']['analyze'] = res['session_db']['analyze'].astype(str)
    
    # Get list of sessions
    res['session_list'] = list(res['session_db'][
        res['session_db'].analyze == 'True'].index)

    return res

# Linking functions between RS and kkpandas objects that are specific
# to my data
def session2rs(session_name):
    gets = getstarted()
    kk_servers, data_dirs = gets['kk_servers'], gets['data_dirs']
    
    for ratname, kk_server in kk_servers.items():
        if session_name not in kk_server.session_list:
            continue
        
        # Session found
        data_dir = data_dirs[ratname]
        rs = RecordingSession.RecordingSession(
            os.path.join(data_dir, session_name))
        
        return rs
    
    # No session ever found
    raise ValueError("No session like %s found!" % session_name)

def session2kk_server(session_name):
    gets = getstarted()
    kk_servers = gets['kk_servers']
    
    for ratname, kk_server in kk_servers.items():
        if session_name in kk_server.session_list:
            return kk_server
        
    raise ValueError("No session like %s found!" % session_name)