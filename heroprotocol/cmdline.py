#!/usr/bin/env python
#
# Copyright (c) 2015 Blizzard Entertainment
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import os
import sys
import argparse
import importlib
import pprint
import json

from mpyq import MPQArchive

from heroprotocol.protocols import protocol29406

gameEventsList = []
trackerEventsList = []
replayFile = ""
composite = ""
protocol = ""

class EventLogger:
    
    def __init__(self):
        self._event_stats = {}
        
    def log(self, output, event):

        self.buildEventStats(output, event)
        
        # write structure
        pprint.pprint(event, stream=output)
        
    def log_stats(self, output):
        for name, stat in sorted(self._event_stats.iteritems(), key=lambda x: x[1][1]):
            print >> output, '"%s", %d, %d,' % (name, stat[0], stat[1] / 8)

    def buildEventStats(self, output, event):

        # update stats
        if '_event' in event and '_bits' in event:
            stat = self._event_stats.get(event['_event'], [0, 0])
            stat[0] += 1  # count of events
            stat[1] += event['_bits']  # count of bits
            self._event_stats[event['_event']] = stat


    def createStats(self, output, type, event):

        self.buildEventStats(output, event)
        
        if type == 'trackerEvents':
            trackerEventsList.append(event)

        if type == 'gameEvents':
            gameEventsList.append(event)

    def parseComposite(self, protocol, archive):

        # Replay Details
        contentsDetails = archive.read_file('replay.details')
        details = {}
        details = protocol.decode_replay_details(contentsDetails)
        if "m_cacheHandles" in details:
            del details["m_cacheHandles"]

        # Replay Game Events
        contentsGameEvents = archive.read_file('replay.game.events')
        for event in protocol.decode_replay_game_events(contentsGameEvents):
            logger.createStats(sys.stdout, 'gameEvents', event)

        # Replay Tracker Events
        if hasattr(protocol, 'decode_replay_tracker_events'):
            contentsTrackerEvents = archive.read_file('replay.tracker.events')
            for event in protocol.decode_replay_tracker_events(contentsTrackerEvents):
                logger.createStats(sys.stdout, 'trackerEvents', event)

        # Build & print the composite object
        compositeObject = {}
        compositeObject["details"] = details
        compositeObject["gameEvents"] = gameEventsList
        compositeObject["trackerEvents"] = trackerEventsList

        self.dumpComposite(compositeObject)

    # dump as JSON
    def dumpComposite(self, compositeObject):
        global composite 
        
        composite = json.dumps(compositeObject)

        return composite

    def logComposite(self, output, compositeObject):
        print compositeObject

logger = EventLogger()

def main(replayFile=None, protocol=protocol):
    """Main entry point from the command line."""
    parser = argparse.ArgumentParser()
    parser.add_argument('--replay_file', help='.StormReplay file to load')
    parser.add_argument("--gameevents", help="print game events",
                        action="store_true")
    parser.add_argument("--messageevents", help="print message events",
                        action="store_true")
    parser.add_argument("--trackerevents", help="print tracker events",
                        action="store_true")
    parser.add_argument("--attributeevents", help="print attributes events",
                        action="store_true")
    parser.add_argument("--header", help="print protocol header",
                        action="store_true")
    parser.add_argument("--details", help="print protocol details",
                        action="store_true")
    parser.add_argument("--initdata", help="print protocol initdata",
                        action="store_true")
    parser.add_argument("--stats", help="print stats",
                        action="store_true")
    parser.add_argument("--composite", help="build composite stats and print them as JSON", 
                        action="store_true")

    args = parser.parse_args()

    if replayFile is None:
        archive = MPQArchive(args.replay_file)
    else:
        archive = MPQArchive(replayFile)

    # Read the protocol header, this can be read with any protocol
    contents = archive.header['user_data_header']['content']
    header = protocol29406.decode_replay_header(contents)
    if args.header:
        logger.log(sys.stdout, header)

    # The header's baseBuild determines which protocol to use
    baseBuild = header['m_version']['m_baseBuild']
    try:
        protocol = importlib.import_module('heroprotocol.protocols.protocol%s' % (baseBuild,))
    except:
        print >> sys.stderr, 'Unsupported base build: %d' % baseBuild
        sys.exit(1)
        
    # Print protocol details
    if args.details:
        contents = archive.read_file('replay.details')
        details = protocol.decode_replay_details(contents)
        logger.log(sys.stdout, details)

    # Print protocol init data
    if args.initdata:
        contents = archive.read_file('replay.initData')
        initdata = protocol.decode_replay_initdata(contents)
        logger.log(sys.stdout, initdata['m_syncLobbyState']['m_gameDescription']['m_cacheHandles'])
        logger.log(sys.stdout, initdata)

    # Print game events and/or game events stats
    if args.gameevents:
        contents = archive.read_file('replay.game.events')
        for event in protocol.decode_replay_game_events(contents):
            logger.log(sys.stdout, event)

    # Print message events
    if args.messageevents:
        contents = archive.read_file('replay.message.events')
        for event in protocol.decode_replay_message_events(contents):
            logger.log(sys.stdout, event)

    # Print tracker events
    if args.trackerevents:
        if hasattr(protocol, 'decode_replay_tracker_events'):
            contents = archive.read_file('replay.tracker.events')
            for event in protocol.decode_replay_tracker_events(contents):
                logger.log(sys.stdout, event)

    # Print attributes events
    if args.attributeevents:
        contents = archive.read_file('replay.attributes.events')
        attributes = protocol.decode_replay_attributes_events(contents)
        logger.log(sys.stdout, attributes)
        
    # Print stats
    if args.stats:
        logger.log_stats(sys.stderr)

    # Build Composite Stats
    if args.composite:
        logger.parseComposite(protocol, archive)

        logger.logComposite(sys.stdout, composite)

    else:
        logger.parseComposite(protocol, archive)
        return composite
