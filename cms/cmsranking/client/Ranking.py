# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2011 Luca Wehrstedt <luca.wehrstedt@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from DataStore import DataStore
from HistoryStore import HistoryStore
from UserDetail import UserDetail
from Scoreboard import Scoreboard
from TeamSearch import TeamSearch
from Overview import Overview
from TimeView import TimeView

import pyjd


class Ranking:
    def data_loaded(self):
        self.hs = HistoryStore(self.ds)
        self.up = UserDetail(self.ds, self.hs)
        self.sb = Scoreboard(self.ds, self.up)

#        self.ts = TeamSearch(self.ds)
#        self.ov = Overview(self.ds)
        self.tv = TimeView(self.ds)

    def onModuleLoad(self):
        self.ds = DataStore(self.data_loaded)

if __name__ == '__main__':
    pyjd.setup("./public/Ranking.html")
    app = Ranking()
    app.onModuleLoad()
    pyjd.run()
