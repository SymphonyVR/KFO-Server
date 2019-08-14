# TsuserverDR, a Danganronpa Online server based on tsuserver3, an Attorney Online server
#
# Copyright (C) 2016 argoneus <argoneuscze@gmail.com> (original tsuserver3)
# Current project leader: 2018-19 Chrezm/Iuvee <thechrezm@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import datetime
import time

from server import client_changearea
from server import fantacrypt
from server import logger
from server.exceptions import ClientError, PartyError
from server.constants import TargetType, Constants

class ClientManager:
    class Client:
        def __init__(self, server, transport, user_id, ipid, my_protocol=None, ip=None):
            self.server = server
            self.transport = transport
            self.area_changer = client_changearea.ClientChangeArea(self)
            self.can_join = 0 # Needs to be 2 to actually connect
            self.can_askchaa = True # Needs to be true to process an askchaa packet
            self.version = ('Undefined', 'Undefined') # AO version used, established through ID pack

            self.hdid = ''
            self.ipid = ipid
            self.id = user_id
            self.char_id = None
            self.name = ''
            self.fake_name = ''
            self.char_folder = ''
            self.pos = ''

            self.area = server.area_manager.default_area()
            self.party = None
            self.is_mod = False
            self.is_gm = False
            self.is_dj = True
            self.is_cm = False
            self.pm_mute = False
            self.evi_list = []
            self.disemvowel = False
            self.remove_h = False
            self.disemconsonant = False
            self.gimp = False
            self.muted_global = False
            self.muted_adverts = False
            self.is_muted = False
            self.is_ooc_muted = False
            self.pm_mute = False
            self.mod_call_time = 0
            self.in_rp = False
            self.is_visible = True
            self.multi_ic = None
            self.multi_ic_pre = ''
            self.showname = ''
            self.following = None
            self.followedby = set()
            self.music_list = None
            self.autopass = False
            self.showname_history = list()
            self.is_transient = False
            self.handicap_backup = None # Use if custom handicap is overwritten with a server one
            self.is_movement_handicapped = False
            self.show_shownames = True
            self.is_bleeding = False
            self.get_foreign_rolls = False
            self.last_sent_clock = None
            self.last_ic_message = ''
            self.last_ooc_message = ''
            self.joined = time.time()
            self.last_active = Constants.get_time()
            self.first_person = False
            self.last_ic_notme = None, None
            self.is_blind = False
            self.is_deaf = False
            self.is_gagged = False

            #music flood-guard stuff
            self.mus_counter = 0
            self.mute_time = 0
            self.mflood_interval = self.server.config['music_change_floodguard']['interval_length']
            self.mflood_times = self.server.config['music_change_floodguard']['times_per_interval']
            self.mflood_mutelength = self.server.config['music_change_floodguard']['mute_length']
            self.mus_change_time = [x * self.mflood_interval for x in range(self.mflood_times)]

        def send_raw_message(self, msg):
            self.transport.write(msg.encode('utf-8'))

        def send_command(self, command, *args):
            if args:
                if command == 'MS':
                    for evi_num in range(len(self.evi_list)):
                        if self.evi_list[evi_num] == args[11]:
                            lst = list(args)
                            lst[11] = evi_num
                            args = tuple(lst)
                            break
                self.send_raw_message('{}#{}#%'.format(command, '#'.join([str(x) for x in args])))
            else:
                self.send_raw_message('{}#%'.format(command))

        def send_ooc(self, msg, allow_empty=False, is_staff=None, in_area=None, pred=None,
                     not_to=None, to_blind=None, to_deaf=None):
            if not allow_empty and not msg:
                return

            cond = self._build_cond(is_staff=is_staff, in_area=in_area, pred=pred, not_to=not_to,
                                    to_blind=to_blind, to_deaf=to_deaf)

            if cond(self):
                self.send_command('CT', self.server.config['hostname'], msg)

        def send_ooc_others(self, msg, allow_empty=False, is_staff=None, in_area=None, pred=None,
                            not_to=None, to_blind=None, to_deaf=None):
            if not allow_empty and not msg:
                return

            if not_to is None:
                not_to = set()

            cond = self._build_cond(is_staff=is_staff, in_area=in_area, pred=pred,
                                    not_to=not_to.union({self}), to_blind=to_blind,
                                    to_deaf=to_deaf)
            self.server.send_all_cmd_pred('CT', self.server.config['hostname'], msg, pred=cond)

        def _build_cond(self, is_staff=None, in_area=None, pred=None, not_to=None, to_blind=None,
                        to_deaf=None):
            conditions = list()

            if is_staff is True:
                conditions.append(lambda c: c.is_staff())
            elif is_staff is False:
                conditions.append(lambda c: not c.is_staff())
            elif is_staff is None:
                pass
            else:
                raise KeyError('Invalid argument for _build_cond is_staff: {}'.format(is_staff))

            if in_area is True:
                conditions.append(lambda c: c.area == self.area)
            elif in_area is False:
                conditions.append(lambda c: c.area != self.area)
            elif type(in_area) is type(self.area): # Lazy way of checking if in_area is an area obj
                conditions.append(lambda c: c.area == in_area)
            elif in_area is None:
                pass
            else:
                raise KeyError('Invalid argument for _build_cond in_area: {}'.format(in_area))

            if pred is not None:
                conditions.append(pred)

            if not_to is not None:
                conditions.append(lambda c: c not in not_to)

            if to_blind is True:
                conditions.append(lambda c: c.is_blind)
            elif to_blind is False:
                conditions.append(lambda c: not c.is_blind)
            elif to_blind is None:
                pass
            else:
                raise KeyError('Invalid argument for _build_cond to_blind: {}'.format(to_blind))

            if to_deaf is True:
                conditions.append(lambda c: c.is_deaf)
            elif to_deaf is False:
                conditions.append(lambda c: not c.is_deaf)
            elif to_deaf is None:
                pass
            else:
                raise KeyError('Invalid argument for _build_cond to_deaf: {}'.format(to_deaf))

            cond = lambda c: all([cond(c) for cond in conditions])

            return cond

        def send_motd(self):
            self.send_ooc('=== MOTD ===\r\n{}\r\n============='.format(self.server.config['motd']))

        def is_valid_name(self, name):
            name_ws = name.replace(' ', '')
            if not name_ws or name_ws.isdigit():
                return False
            #for client in self.server.client_manager.clients:
                #print(client.name == name)
                #if client.name == name:
                    #return False
            return True

        def disconnect(self):
            self.transport.close()

        def change_character(self, char_id, force=False, target_area=None):
            # Added target_area parameter because when switching areas, the change character code
            # is run before the character's area actually changes, so it would look for the wrong
            # area if I just did self.area
            if target_area is None:
                target_area = self.area

            if not self.server.is_valid_char_id(char_id):
                raise ClientError('Invalid character ID.')
            if not target_area.is_char_available(char_id, allow_restricted=self.is_staff()):
                if force:
                    for client in self.area.clients:
                        if client.char_id == char_id:
                            client.char_select()
                else:
                    raise ClientError('Character {} not available.'
                                      .format(self.get_char_name(char_id)))

            if self.char_id < 0 and char_id >= 0: # No longer spectator?
                # Now bound by AFK rules
                self.server.create_task(self, ['as_afk_kick', self.area.afk_delay,
                                               self.area.afk_sendto])

            old_char = self.get_char_name()
            self.char_id = char_id
            self.char_folder = self.get_char_name() # Assumes players are not iniswapped initially
            self.pos = ''
            self.send_command('PV', self.id, 'CID', self.char_id)
            logger.log_server('[{}]Changed character from {} to {}.'
                              .format(self.area.id, old_char, self.get_char_name()), self)

        def change_music_cd(self):
            if self.is_mod or self.is_cm:
                return 0
            if self.mute_time:
                if time.time() - self.mute_time < self.mflood_mutelength:
                    return self.mflood_mutelength - (time.time() - self.mute_time)
                self.mute_time = 0

            index = (self.mus_counter - self.mflood_times + 1) % self.mflood_times
            if time.time() - self.mus_change_time[index] < self.mflood_interval:
                self.mute_time = time.time()
                return self.mflood_mutelength

            self.mus_counter = (self.mus_counter + 1) % self.mflood_times
            self.mus_change_time[self.mus_counter] = time.time()
            return 0

        def reload_character(self):
            self.change_character(self.char_id, True)

        def reload_music_list(self, new_music_file=None):
            """
            Rebuild the music list so that it only contains the target area's
            reachable areas+music. Useful when moving areas/logging in or out.
            """
            if new_music_file:
                new_music_list = self.server.load_music(music_list_file=new_music_file,
                                                        server_music_list=False)
                self.music_list = new_music_list
                self.server.build_music_list_ao2(from_area=self.area, c=self,
                                                 music_list=new_music_list)
            else:
                self.server.build_music_list_ao2(from_area=self.area, c=self)
            # KEEP THE ASTERISK, unless you want a very weird single area comprised
            # of all areas back to back forming a black hole area of doom and despair
            # that crashes all clients that dare attempt join this area.
            self.send_command('FM', *self.server.music_list_ao2)

        def check_change_area(self, area, override_passages=False, override_effects=False,
                              more_unavail_chars=None):
            checker = self.area_changer.check_change_area
            results = checker(area, override_passages=override_passages,
                              override_effects=override_effects,
                              more_unavail_chars=more_unavail_chars)
            return results

        def notify_change_area(self, area, old_char, ignore_bleeding=False, just_me=False):
            notifier = self.area_changer.notify_change_area
            notifier(area, old_char, ignore_bleeding=ignore_bleeding, just_me=just_me)

        def change_area(self, area, override_all=False, override_passages=False,
                        override_effects=False, ignore_bleeding=False, ignore_followers=False,
                        ignore_checks=False, ignore_notifications=False, more_unavail_chars=None,
                        change_to=None, from_party=False):
            changer = self.area_changer.change_area
            changer(area, override_all=override_all, override_passages=override_passages,
                    override_effects=override_effects, ignore_bleeding=ignore_bleeding,
                    ignore_followers=ignore_followers, ignore_checks=ignore_checks,
                    ignore_notifications=ignore_notifications, change_to=change_to,
                    more_unavail_chars=more_unavail_chars, from_party=from_party)

        def change_showname(self, showname, target_area=None, forced=True):
            # forced=True means that someone else other than the user themselves requested the showname change.
            # Should only be false when using /showname.
            if target_area is None:
                target_area = self.area

            # Check length
            if len(showname) > self.server.config['showname_max_length']:
                raise ClientError("Given showname {} exceeds the server's character limit of {}."
                                  .format(showname, self.server.config['showname_max_length']))

            # Check if non-empty showname is already used within area
            if showname != '':
                for c in target_area.clients:
                    if c.showname == showname and c != self:
                        raise ValueError("Given showname {} is already in use in this area."
                                         .format(showname))
                        # This ValueError must be recaught, otherwise the client will crash.

            if self.showname != showname:
                status = {True: 'Was', False: 'Self'}

                if showname != '':
                    self.showname_history.append("{} | {} set to {}"
                                                 .format(Constants.get_time(), status[forced], showname))
                else:
                    self.showname_history.append("{} | {} cleared"
                                                 .format(Constants.get_time(), status[forced]))
            self.showname = showname

        def change_visibility(self, new_status):
            if new_status: # Changed to visible (e.g. through /reveal)
                self.send_ooc("You are no longer sneaking.")
                self.is_visible = True

                # Player should also no longer be under the effect of the server's sneaked handicap.
                # Thus, we check if there existed a previous movement handicap that had a shorter delay
                # than the server's sneaked handicap and restore it (as by default the server will take the
                # largest handicap when dealing with the automatic sneak handicap)
                try:
                    _, _, name, _ = self.server.get_task_args(self, ['as_handicap'])
                except KeyError:
                    pass
                else:
                    if name == "Sneaking":
                        if self.server.config['sneak_handicap'] > 0 and self.handicap_backup:
                            # Only way for a handicap backup to exist and to be in this situation is
                            # for the player to had a custom handicap whose length was shorter than the server's
                            # sneak handicap, then was set to be sneaking, then was revealed.
                            # From this, we can recover the old handicap backup
                            _, old_length, old_name, old_announce_if_over = self.handicap_backup[1]

                            msg = ('{} was automatically imposed their old movement handicap "{}" '
                                   'of length {} seconds after being revealed in area {} ({}).')
                            self.send_ooc_others(msg.format(self.get_char_name(), old_name, old_length, self.area.name, self.area.id),
                                                 is_staff=True)
                            self.send_ooc('You were automatically imposed your former movement '
                                          'handicap "{}" of length {} seconds when changing areas.'
                                          .format(old_name, old_length))
                            self.server.create_task(self, ['as_handicap', time.time(), old_length, old_name, old_announce_if_over])
                        else:
                            self.server.remove_task(self, ['as_handicap'])

                logger.log_server('{} is no longer sneaking.'.format(self.ipid), self)
            else: # Changed to invisible (e.g. through /sneak)
                self.send_ooc("You are now sneaking.")
                self.is_visible = False

                # Check to see if should impose the server's sneak handicap on the player
                # This should only happen if two conditions are satisfied:
                # 1. There is a positive sneak handicap and,
                # 2. The player has no movement handicap or, if they do, it is shorter than the sneak handicap
                if self.server.config['sneak_handicap'] > 0:
                    try:
                        _, length, _, _ = self.server.get_task_args(self, ['as_handicap'])
                        if length < self.server.config['sneak_handicap']:
                            self.send_ooc_others('{} was automatically imposed the longer movement handicap "Sneaking" of length {} seconds in area {} ({}).'
                                                 .format(self.get_char_name(), self.server.config['sneak_handicap'], self.area.name, self.area.id),
                                                 is_staff=True)
                            raise KeyError # Lazy way to get there, but it works
                    except KeyError:
                        self.send_ooc('You were automatically imposed a movement handicap '
                                      '"Sneaking" of length {} seconds when changing areas.'
                                      .format(self.server.config['sneak_handicap']))
                        self.server.create_task(self, ['as_handicap', time.time(), self.server.config['sneak_handicap'], "Sneaking", True])

                logger.log_server('{} is now sneaking.'.format(self.ipid), self)

        def follow_user(self, target):
            if target == self:
                raise ClientError('You cannot follow yourself.')
            if target == self.following:
                raise ClientError('You are already following that player.')

            self.send_ooc('Began following client {} at {}'.format(target.id, Constants.get_time()))

            # Notify the player you were following before that you are no longer following them
            # and with notify I mean internally.
            if self.following:
                self.following.followedby.remove(self)
            self.following = target
            target.followedby.add(self)

            if self.area != target.area:
                self.follow_area(target.area, just_moved=False)

        def unfollow_user(self):
            if not self.following:
                raise ClientError('You are not following anyone.')

            self.send_ooc("Stopped following client {} at {}."
                          .format(self.following.id, Constants.get_time()))
            self.following.followedby.remove(self)
            self.following = None

        def follow_area(self, area, just_moved=True):
            # just_moved if True assumes the case where the followed user just moved
            # It being false is the case where, when the following started, the followed user was in another area, and thus the followee is moved automtically
            if just_moved:
                self.send_ooc('Followed user moved to {} at {}'
                              .format(area.name, Constants.get_time()))
            else:
                self.send_ooc('Followed user was at {}'.format(area.name))

            try:
                self.change_area(area, ignore_followers=True)
            except ClientError as error:
                self.send_ooc('Unable to follow to {}: {}'.format(area.name, error))

        def send_area_list(self):
            msg = '=== Areas ==='
            lock = {True: '[LOCKED]', False: ''}
            for i, area in enumerate(self.server.area_manager.areas):
                owner = 'FREE'
                if area.owned:
                    for client in [x for x in area.clients if x.is_cm]:
                        owner = 'MASTER: {}'.format(client.get_char_name())
                        break
                locked = area.is_gmlocked or area.is_modlocked or area.is_locked

                if self.is_staff():
                    num_clients = len([c for c in area.clients if c.char_id is not None])
                else:
                    num_clients = len([c for c in area.clients if c.is_visible and c.char_id is not None])

                msg += '\r\nArea {}: {} (users: {}) {}'.format(i, area.name, num_clients, lock[locked])
                if self.area == area:
                    msg += ' [*]'
            self.send_ooc(msg)

        def send_limited_area_list(self):
            msg = '=== Areas ==='
            for i, area in enumerate(self.server.area_manager.areas):
                msg += '\r\nArea {}: {}'.format(i, area.name)
                if self.area == area:
                    msg += ' [*]'
            self.send_ooc(msg)

        def get_area_info(self, area_id, mods, as_mod=None, include_shownames=False,
                          only_my_multiclients=False):
            if as_mod is None:
                as_mod = self.is_mod or self.is_cm # Cheap, but decent

            area = self.server.area_manager.get_area_by_id(area_id)
            info = '== Area {}: {} =='.format(area.id, area.name)

            sorted_clients = []

            for c in area.clients:
                # Conditions to print out a client in /getarea(s)
                # * Client is not in the server selection screen and,
                # * Any of the four
                # 1. Client is yourself.
                # 2. You are a staff member.
                # 3. Client is visible.
                # 4. Client is a mod when requiring only mods be printed.

                # If only_my_multiclients is set to True, only the clients opened by the current
                # user will be listed. Useful for /multiclients.
                if c.char_id is not None:
                    cond = (c == self or self.is_staff() or c.is_visible or (mods and c.is_mod))
                    multiclient_cond = (not (only_my_multiclients and c.ipid != self.ipid))

                    if cond and multiclient_cond:
                        sorted_clients.append(c)

            sorted_clients = sorted(sorted_clients, key=lambda x: x.get_char_name())

            for c in sorted_clients:
                info += '\r\n[{}] {}'.format(c.id, c.get_char_name())
                if include_shownames and c.showname != '':
                    info += ' ({})'.format(c.showname)
                if not c.is_visible:
                    info += ' (S)'
                if as_mod:
                    info += ' ({})'.format(c.ipid)
            return len(sorted_clients), info

        def send_area_info(self, current_area, area_id, mods, as_mod=None, include_shownames=False,
                           only_my_multiclients=False):
            info = self.prepare_area_info(current_area, area_id, mods, as_mod=as_mod,
                                          include_shownames=include_shownames,
                                          only_my_multiclients=only_my_multiclients)
            if area_id == -1:
                info = '== Area List ==' + info
            self.send_ooc(info)

        def prepare_area_info(self, current_area, area_id, mods, as_mod=None,
                              include_shownames=False, only_my_multiclients=False):
            #If area_id is -1, then return all areas.
            #If mods is True, then return only mods
            #If include_shownames is True, then include non-empty custom shownames.
            #If only_my_multiclients is True, then include only clients opened by the current player
            # Verify that it should send the area info first
            if not self.is_staff():
                getareas_restricted = (area_id == -1 and not self.area.rp_getareas_allowed)
                getarea_restricted = (area_id != -1 and not self.area.rp_getarea_allowed)
                if getareas_restricted or getarea_restricted:
                    raise ClientError('This command has been restricted to authorized users only '
                                      'in this area while in RP mode.')
                if not self.area.lights:
                    raise ClientError('The lights are off. You cannot see anything.')

            # All code from here on assumes the area info will be sent successfully
            info = ''
            if area_id == -1:
                # all areas info
                unrestricted_access_area = '<ALL>' in current_area.reachable_areas
                for (i, area) in enumerate(self.server.area_manager.areas):
                    # Get area i details...
                    # If staff and there are clients in the area OR
                    # If not staff, there are visible clients in the area, and the area is reachable from the current one
                    not_staff_check = len([c for c in area.clients if c.is_visible or c == self]) > 0 and \
                                      (unrestricted_access_area or area.name in current_area.reachable_areas or self.is_transient)

                    if (self.is_staff() and len(area.clients) > 0) or \
                    (not self.is_staff() and not_staff_check):
                        num, ainfo = self.get_area_info(i, mods, as_mod=as_mod,
                                                        include_shownames=include_shownames,
                                                        only_my_multiclients=only_my_multiclients)
                        if num:
                            info += '\r\n{}'.format(ainfo)
            else:
                _, info = self.get_area_info(area_id, mods, include_shownames=include_shownames)

            return info

        def send_area_hdid(self, area_id):
            info = self.get_area_hdid(area_id)
            self.send_ooc(info)

        def get_area_hdid(self, area_id):
            raise NotImplementedError

        def send_all_area_hdid(self):
            info = '== HDID List =='
            for i in range(len(self.server.area_manager.areas)):
                if len(self.server.area_manager.areas[i].clients) > 0:
                    info += '\r\n{}'.format(self.get_area_hdid(i))
            self.send_ooc(info)

        def send_all_area_ip(self):
            info = '== IP List =='
            for i in range(len(self.server.area_manager.areas)):
                if len(self.server.area_manager.areas[i].clients) > 0:
                    info += '\r\n{}'.format(self.get_area_ip(i))
            self.send_ooc(info)

        def get_area_ip(self, ip):
            raise NotImplementedError

        def send_done(self):
            avail_char_ids = set(range(len(self.server.char_list))) - self.area.get_chars_unusable(allow_restricted=self.is_staff())
            # Readd sneaked players if needed so that they don't appear as taken
            # Their characters will not be able to be reused, but at least that's one less clue about their presence.
            if not self.is_staff():
                avail_char_ids |= {c.char_id for c in self.area.clients if not c.is_visible}

            char_list = [-1] * len(self.server.char_list)
            for x in avail_char_ids:
                char_list[x] = 0
            self.send_command('CharsCheck', *char_list)
            self.send_command('HP', 1, self.area.hp_def)
            self.send_command('HP', 2, self.area.hp_pro)
            self.send_command('BN', self.area.background)
            self.send_command('LE', *self.area.get_evidence_list(self))
            self.send_command('MM', 1)
            self.send_command('OPPASS', fantacrypt.fanta_encrypt(self.server.config['guardpass']))
            if self.char_id is None:
                self.char_id = -1 # Set to a valid ID if still needed
            self.send_command('DONE')

        def char_select(self):
            self.char_id = -1
            self.send_done()

        def get_party(self, tc=False):
            if not self.party:
                raise PartyError('You are not part of a party.')
            return self.party

        def is_staff(self):
            """
            Returns True if logged in as 'any' staff role.
            """
            return self.is_mod or self.is_cm or self.is_gm

        def login(self, arg, auth_command, role):
            """
            Wrapper function for the login method for all roles (GM, CM, Mod)
            """
            if len(arg) == 0:
                raise ClientError('You must specify the password.')
            auth_command(arg)

            if self.area.evidence_mod == 'HiddenCM':
                self.area.broadcast_evidence_list()
            self.reload_music_list() # Update music list to show all areas
            self.send_ooc('Logged in as a {}.'.format(role))
            logger.log_server('Logged in as a {}.'.format(role), self)

        def auth_mod(self, password):
            if self.is_mod:
                raise ClientError('Already logged in.')
            if password == self.server.config['modpass']:
                self.is_mod = True
                self.is_cm = False
                self.is_gm = False
                self.in_rp = False
            else:
                raise ClientError('Invalid password.')

        def auth_cm(self, password):
            if self.is_cm:
                raise ClientError('Already logged in.')
            if password == self.server.config['cmpass']:
                self.is_cm = True
                self.is_mod = False
                self.is_gm = False
                self.in_rp = False
            else:
                raise ClientError('Invalid password.')

        def auth_gm(self, password):
            if self.is_gm:
                raise ClientError('Already logged in.')

            # Obtain the daily gm pass (changes at 3 pm server time)
            current_day = datetime.datetime.today().weekday()
            if datetime.datetime.now().hour < 15:
                current_day += 1
            daily_gmpass = self.server.config['gmpass{}'.format((current_day % 7) + 1)]

            valid_passwords = [self.server.config['gmpass']]
            if daily_gmpass is not None:
                valid_passwords.append(daily_gmpass)

            if password in valid_passwords:
                self.is_gm = True
                self.is_mod = False
                self.is_cm = False
                self.in_rp = False
            else:
                raise ClientError('Invalid password.')

        def get_hdid(self):
            return self.hdid

        def get_ip(self):
            return self.ipid

        def get_ipreal(self):
            return self.transport.get_extra_info('peername')[0]

        def get_char_name(self, char_id=None):
            if char_id is None:
                char_id = self.char_id

            if char_id == -1:
                return self.server.config['spectator_name']
            if char_id is None:
                return 'SERVER_SELECT'
            return self.server.char_list[char_id]

        def get_showname_history(self):
            info = '== Showname history of client {} =='.format(self.id)

            if len(self.showname_history) == 0:
                info += '\r\nClient has not changed their showname since joining the server.'
            else:
                for log in self.showname_history:
                    info += '\r\n*{}'.format(log)
            return info

        def change_position(self, pos=''):
            if pos not in ('', 'def', 'pro', 'hld', 'hlp', 'jud', 'wit'):
                raise ClientError('Invalid position. Possible values: def, pro, hld, hlp, jud, wit.')
            self.pos = pos

        def set_mod_call_delay(self):
            self.mod_call_time = round(time.time() * 1000.0 + 30000)

        def can_call_mod(self):
            return (time.time() * 1000.0 - self.mod_call_time) > 0

        def get_multiclients(self):
            return self.server.client_manager.get_targets(self, TargetType.IPID, self.ipid, False)

        def get_info(self, as_mod=False, as_cm=False, identifier=None):
            if identifier is None:
                identifier = self.id

            info = '== Client information of {} =='.format(identifier)
            ipid = self.ipid if as_mod or as_cm else "-"
            hdid = self.hdid if as_mod or as_cm else "-"
            info += '\n*CID: {}. IPID: {}. HDID: {}'.format(self.id, ipid, hdid)
            char_info = self.get_char_name()
            if self.char_folder and self.char_folder != char_info: # Indicate iniswap if needed
                char_info = '{} ({})'.format(char_info, self.char_folder)
            info += ('\n*Character name: {}. Showname: {}. OOC username: {}'
                     .format(char_info, self.showname, self.name))
            info += '\n*In area: {}-{}'.format(self.area.id, self.area.name)
            info += '\n*Last IC message: {}'.format(self.last_ic_message)
            info += '\n*Last OOC message: {}'.format(self.last_ooc_message)
            info += ('\n*Is GM? {}. Is CM? {}. Is mod? {}.'
                     .format(self.is_gm, self.is_cm, self.is_mod))
            info += ('\n*Is sneaking? {}. Is bleeding? {}. Is handicapped? {}'
                     .format(not self.is_visible, self.is_bleeding, self.is_movement_handicapped))
            info += ('\n*Is blinded? {}. Is deafened? {}. Is gagged? {}'
                     .format(self.is_blind, self.is_deaf, self.is_gagged))
            info += ('\n*Is transient? {}. Has autopass? {}. Clients open: {}'
                     .format(self.is_transient, self.autopass, len(self.get_multiclients())))
            info += '\n*Is muted? {}. Is OOC Muted? {}'.format(self.is_muted, self.is_ooc_muted)
            info += '\n*Following: {}'.format(self.following.id if self.following else "-")
            info += '\n*Followed by: {}'.format(", ".join([str(c.id) for c in self.followedby])
                                                if self.followedby else "-")
            info += ('\n*Online for: {}. Last active: {}'
                     .format(Constants.time_elapsed(self.joined), self.last_active))
            return info

        def __repr__(self):
            return ('C::{}:{}:{}:{}:{}:{}:{}'
                    .format(self.id, self.ipid, self.name, self.get_char_name(), self.showname,
                            self.is_staff(), self.area.id))

    def __init__(self, server, client_obj=None):
        if client_obj is None:
            self.client_obj = self.Client

        self.clients = set()
        self.server = server
        self.cur_id = [False] * self.server.config['playerlimit']
        self.client_obj = client_obj

    def new_client(self, transport, client_obj=None, my_protocol=None, ip=None):
        if ip is None:
            ip = transport.get_extra_info('peername')[0]
        ipid = self.server.get_ipid(ip)

        if client_obj is None:
            client_obj = self.Client

        cur_id = -1
        for i in range(self.server.config['playerlimit']):
            if not self.cur_id[i]:
                cur_id = i
                break
        c = client_obj(self.server, transport, cur_id, ipid, my_protocol=my_protocol)
        self.clients.add(c)

        # Check if server is full, and if so, send number of players and disconnect
        if cur_id == -1:
            c.send_command('PN', self.server.get_player_count(),
                           self.server.config['playerlimit'])
            c.disconnect()
            return c
        self.cur_id[cur_id] = True
        self.server.client_tasks[cur_id] = dict()
        return c

    def remove_client(self, client):
        # Clients who are following the now leaving client should no longer follow them
        if client.followedby:
            followedby_copy = client.followedby.copy()
            for c in followedby_copy:
                c.unfollow_user()

        # Clients who were being followed by the now leaving client should no longer have a pointer
        # indicating they are being followed by them
        if client.following:
            client.following.followedby.remove(client)

        if client.id >= 0: # Avoid having pre-clients do this (before they are granted a cID)
            self.cur_id[client.id] = False
            # Cancel client's pending tasks
            for task_id in self.server.client_tasks[client.id].keys():
                self.server.get_task(client, [task_id]).cancel()

        if client.party:
            client.party.remove_member(client)

        self.clients.remove(client)

    def get_targets(self, client, key, value, local=False):
        #possible keys: ip, OOC, id, cname, ipid, hdid
        areas = None
        if local:
            areas = [client.area]
        else:
            areas = client.server.area_manager.areas
        targets = []
        if key == TargetType.ALL:
            for nkey in range(6):
                targets += self.get_targets(client, nkey, value, local)
        for area in areas:
            for c in area.clients:
                if key == TargetType.IP:
                    if value.lower().startswith(c.get_ipreal().lower()):
                        targets.append(c)
                elif key == TargetType.OOC_NAME:
                    if value.lower().startswith(c.name.lower()) and c.name:
                        targets.append(c)
                elif key == TargetType.CHAR_NAME:
                    if value.lower().startswith(c.get_char_name().lower()):
                        targets.append(c)
                elif key == TargetType.ID:
                    if c.id == value:
                        targets.append(c)
                elif key == TargetType.IPID:
                    if c.ipid == value:
                        targets.append(c)
                elif key == TargetType.HDID:
                    if c.hdid == value:
                        targets.append(c)
        return targets

    def get_muted_clients(self):
        clients = []
        for client in self.clients:
            if client.is_muted:
                clients.append(client)
        return clients

    def get_ooc_muted_clients(self):
        clients = []
        for client in self.clients:
            if client.is_ooc_muted:
                clients.append(client)
        return clients
