# -*- coding: utf-8 -*-
# DEPS:
# sudo apt install python3-flask python3-mysqldb python3-wtforms
#                  gunicorn3 nginx apache2-utils mailutils
import MySQLdb
from flask import Flask, render_template, request
from wtforms import Form, StringField, validators
from sys import exit
from time import time


configINI = "/etc/mattermost-manager.ini"
try:
    import configparser
    config = configparser.ConfigParser()
    config.readfp(open(configINI))
    DB_HOST = config.get("database", "host")
    DB_NAME = config.get("database", "name")
    DB_USER = config.get("database", "user")
    DB_PASS = config.get("database", "password")
except Exception as e:
    print("CONFIG_ERROR: %s" % (e))
    exit(1)


app = Flask(__name__)
app.debug = True


def connection():
    conn = MySQLdb.connect(host= DB_HOST,
                           user = DB_USER,
                           passwd = DB_PASS,
                           db = DB_NAME,
                           charset='utf8')
    c = conn.cursor(MySQLdb.cursors.DictCursor)
    return c, conn


def range_to_epoch(timevalue):
    # All, 36hrs, 7days, 31days, 90days
    if timevalue in (129600, 604800, 2678400, 7776000):
        return ((int(time())-timevalue)*1000)
    else:
        # Default to 36hrs
        return ((time()-129600)*1000)


@app.route('/')
def index():
    try:
        c, conn = connection()
        result = c.execute("""SELECT Status, COUNT(Status) AS StateCount
                                FROM Status GROUP BY Status""")
        status = c.fetchall()

        if result > 0:
            return render_template('home.html', status=status)
        else:
            msg = 'No Status Found'
            return render_template('home.html', msg=msg)

        c.close()
    except Exception as e:
        return(str(e))


@app.route('/users')
def users():
    try:
        c, conn = connection()
        result = \
            c.execute("""SELECT
                           Id, Username, Nickname, FirstName, LastName, Email,
                           CASE WHEN DeleteAt = 0 THEN ''
                              ELSE
                                FROM_UNIXTIME(SUBSTR(DeleteAt, 1, 10))
                              END AS Deleted
                         FROM Users
                           ORDER BY Username""")
        users = c.fetchall()

        if result > 0:
            return render_template('users.html', users=users)
        else:
            msg = 'No Users Found'
            return render_template('users.html', msg=msg)

        c.close()
    except Exception as e:
        return(str(e))


@app.route('/user/<string:id>/')
def user(id):
    c, conn = connection()
    result = c.execute("""SELECT Users.Id, Users.Username, Users.FirstName,
                                 Users.LastName, Users.Nickname, Users.Roles,
                                 Users.Email, Users.EmailVerified, TeamId,
                                 Teams.Name, Teams.DisplayName,
                            CASE WHEN Users.DeleteAt = 0 THEN ''
                              ELSE
                                FROM_UNIXTIME(SUBSTR(Users.DeleteAt, 1, 10))
                              END AS Deleted
                          FROM Users
                              LEFT JOIN TeamMembers ON Users.Id = UserId
                              LEFT JOIN Teams ON TeamId = Teams.Id
                          WHERE Users.Id = %s""", [id])

    user = c.fetchall()

    return render_template('user.html', user=user)


@app.route('/channels')
def channels():
    try:
        c, conn = connection()
        result = \
            c.execute("""SELECT Id, DisplayName, Name, TotalMsgCount,
                            CASE WHEN (SUBSTR(LastPostAt,1,10) -
                                SUBSTR(CreateAt,1,10)) < 86400 THEN TotalMsgCount
                            ELSE ROUND( (TotalMsgCount * 86400) /
                                ( SUBSTR(LastPostAt,1,10) -
                                    SUBSTR(CreateAt,1,10)) )
                            END AS MPD,
                           FROM_UNIXTIME(SUBSTR(CreateAt, 1, 10))
                              AS Created,
                           CASE WHEN DeleteAt = 0 THEN ''
                              ELSE
                                FROM_UNIXTIME(SUBSTR(DeleteAt, 1, 10))
                              END AS Deleted,
                           FROM_UNIXTIME(SUBSTR(LastPostAt, 1, 10))
                              AS LastPosted
                           FROM Channels
                         WHERE Name NOT LIKE '%%\_\_%%'
                           ORDER BY Name""")
        channels = c.fetchall()

        if result > 0:
            return render_template('channels.html', channels=channels)
        else:
            msg = 'No Channels Found'
            return render_template('channels.html', msg=msg)

        c.close()
    except Exception as e:
        return(str(e))


### UPDATE Channels SET DeleteAt = 0 WHERE Id = "7eog98md57rjdfdcth7frmzttw";
@app.route('/channel/<string:id>/')
def channel(id):
    c, conn = connection()
    result = c.execute("""SELECT Channels.Id, Channels.Name, Channels.DisplayName,
                                 Users.Id AS UserId, Users.Username,
                            FROM_UNIXTIME(SUBSTR(Channels.CreateAt, 1, 10))
                              AS Created,
                            FROM_UNIXTIME(SUBSTR(Channels.UpdateAt, 1, 10))
                              AS Updated,
                            CASE WHEN Channels.DeleteAt = 0 THEN 0
                              ELSE
                                FROM_UNIXTIME(SUBSTR(Channels.DeleteAt, 1, 10))
                              END AS Deleted,
                            FROM_UNIXTIME(SUBSTR(Channels.LastPostAt, 1, 10))
                              AS LastPosted,
                            Creator.Username AS created_by
                          FROM Channels
                            LEFT JOIN ChannelMembers ON Channels.Id = ChannelMembers.ChannelId
                            LEFT JOIN Users ON Users.Id = ChannelMembers.UserId
                            LEFT JOIN Users AS Creator ON Channels.CreatorId = Creator.Id
                          WHERE Channels.Id = %s""", [id])

    channel = c.fetchall()

    return render_template('channel.html', channel=channel)


@app.route('/public_channels')
def public_channels():
    try:
        c, conn = connection()
        result = \
            c.execute("""SELECT PublicChannels.Id, PublicChannels.DisplayName,
                           PublicChannels.Name, TeamId,
                             Teams.DisplayName AS TeamDisplayName,
                           CASE WHEN PublicChannels.DeleteAt = 0 THEN ''
                              ELSE
                                FROM_UNIXTIME(SUBSTR(PublicChannels.DeleteAt, 1, 10))
                              END AS Deleted
                           FROM PublicChannels
                             LEFT JOIN Teams ON TeamId = Teams.Id
                         ORDER BY Name""")
        channels = c.fetchall()

        if result > 0:
            return render_template('public_channels.html', channels=channels)
        else:
            msg = 'No Public Channels Found'
            return render_template('public_channels.html', msg=msg)

        c.close()
    except Exception as e:
        return(str(e))


@app.route('/public_channel/<string:id>/')
def public_channel(id):
    c, conn = connection()
    result = c.execute("""SELECT PublicChannels.*, Teams.Name AS TeamName,
                                Teams.DisplayName AS TeamDisplayName,
                            CASE WHEN PublicChannels.DeleteAt = 0 THEN ''
                              ELSE
                                FROM_UNIXTIME(SUBSTR(PublicChannels.DeleteAt, 1, 10))
                              END AS Deleted
                          FROM PublicChannels
                              LEFT JOIN Teams ON PublicChannels.TeamId = Teams.Id
                          WHERE PublicChannels.Id = %s""", [id])

    channel = c.fetchone()

    return render_template('public_channel.html', channel=channel)


@app.route('/teams')
def teams():
    try:
        c, conn = connection()
        result = \
            c.execute("""SELECT Id, Name, DisplayName, Email,
                           CASE WHEN DeleteAt = 0 THEN ''
                              ELSE
                                FROM_UNIXTIME(SUBSTR(DeleteAt, 1, 10))
                              END AS Deleted
                           FROM Teams
                         ORDER BY Name""")
        teams = c.fetchall()

        if result > 0:
            return render_template('teams.html', teams=teams)
        else:
            msg = 'No Teams Found'
            return render_template('teams.html', msg=msg)

        c.close()
    except Exception as e:
        return(str(e))


@app.route('/team/<string:id>/')
def team(id):
    c, conn = connection()
    result = c.execute("""
        SELECT Teams.Id, Teams.Name, Teams.DisplayName,
                Teams.Email, UserId,
                Users.Username, Users.FirstName, Users.LastName,
        CASE WHEN Teams.DeleteAt = 0 THEN ''
            ELSE
            FROM_UNIXTIME(SUBSTR(Teams.DeleteAt, 1, 10))
            END AS Deleted
        FROM Teams
            LEFT JOIN TeamMembers ON Teams.Id = TeamMembers.TeamId
            LEFT JOIN Users ON TeamMembers.UserId = Users.Id
        WHERE Teams.Id = %s""", [id])

    team = c.fetchall()

    return render_template('team.html', team=team)


@app.route('/posts_by_channel/<string:id>/')
def posts_by_channel(id):
    c, conn = connection()
    result = c.execute("""SELECT
        FROM_UNIXTIME(SUBSTR(Posts.CreateAt, 1, 10)) AS timestamp,
        UserId, Username, Message, ChannelId, Channels.Name,
        Posts.DeleteAt, Posts.EditAt,
        Channels.DisplayName
                FROM Posts
        LEFT JOIN Users ON Posts.UserId = Users.Id
        LEFT JOIN Channels ON Posts.ChannelId = Channels.Id
        WHERE ChannelId = %s
        ORDER BY Posts.CreateAt, Posts.EditAt, Posts.DeleteAt""",
        [id])

    posts = c.fetchall()

    return render_template('posts_by_channel.html', posts=posts)


@app.route('/posts_by_channel_limit/<string:id>/<int:end>/')
def posts_by_channel_limit(id, end):
    c, conn = connection()
    result = c.execute("""SELECT
        FROM_UNIXTIME(SUBSTR(Posts.CreateAt, 1, 10)) AS timestamp,
        UserId, Username, Message, ChannelId, Channels.Name,
        Posts.DeleteAt, Posts.EditAt,
        Channels.DisplayName
                FROM Posts
        LEFT JOIN Users ON Posts.UserId = Users.Id
        LEFT JOIN Channels ON Posts.ChannelId = Channels.Id
        WHERE ChannelId = %s AND Posts.CreateAt >= %s
        ORDER BY Posts.CreateAt, Posts.EditAt, Posts.DeleteAt""",
        [id, range_to_epoch(end)])

    posts = c.fetchall()

    return render_template('posts_by_channel.html', posts=posts)


@app.route('/posts_by_user/<string:id>/')
def posts_by_user(id):
    c, conn = connection()
    result = c.execute("""SELECT
        FROM_UNIXTIME(SUBSTR(Posts.CreateAt, 1, 10)) AS timestamp,
        UserId, Username, Message, ChannelId, TeamId,
        Posts.DeleteAt, Posts.EditAt,
        Teams.DisplayName AS TeamName,
        Channels.Name AS ChannelName,
        Channels.DisplayName
                FROM Posts
        LEFT JOIN Users ON Posts.UserId = Users.Id
        LEFT JOIN Channels ON Posts.ChannelId = Channels.Id
        LEFT JOIN Teams ON Channels.TeamId = Teams.Id
        WHERE UserId = %s
        ORDER BY Posts.CreateAt, Posts.EditAt, Posts.DeleteAt""", [id])

    posts = c.fetchall()

    return render_template('posts_by_user.html', posts=posts)


@app.route('/posts_by_user_limit/<string:id>/<int:end>/')
def posts_by_user_limit(id, end):
    c, conn = connection()
    result = c.execute("""SELECT
        FROM_UNIXTIME(SUBSTR(Posts.CreateAt, 1, 10)) AS timestamp,
        UserId, Username, Message, ChannelId,
        Posts.DeleteAt, Posts.EditAt,
        Channels.Name AS ChannelName, Channels.DisplayName
                FROM Posts
        LEFT JOIN Users ON Posts.UserId = Users.Id
        LEFT JOIN Channels ON Posts.ChannelId = Channels.Id
        WHERE UserId = %s AND Posts.CreateAt >= %s
        ORDER BY Posts.CreateAt, Posts.EditAt, Posts.DeleteAt""",
        [id, range_to_epoch(end)])

    posts = c.fetchall()

    return render_template('posts_by_user.html', posts=posts)


class SearchForm(Form):
    term = StringField('',[validators.Length(min=4,max=50)])


@app.route('/search', methods=['GET','POST'])
def search():
    form = SearchForm(request.form)
    if request.method == 'POST' and form.validate():
        term = form.term.data

        # TODO
        # User Id legth is 26
        # select length(thatField) as len where thatField LIKE '%__%' group by len;

        c, conn = connection()
        result = c.execute("""SELECT
            FROM_UNIXTIME(SUBSTR(Posts.CreateAt, 1, 10)) AS timestamp,
            UserId, Username, Message, ChannelId, TeamId,
            Posts.DeleteAt, Posts.EditAt,
            Teams.DisplayName AS TeamName,
            Channels.Name AS ChannelName,
            Channels.DisplayName
                    FROM Posts
            LEFT JOIN Users ON Posts.UserId = Users.Id
            LEFT JOIN Channels ON Posts.ChannelId = Channels.Id
            LEFT JOIN Teams ON Channels.TeamId = Teams.Id
            WHERE Message LIKE %s
            ORDER BY Posts.CreateAt, Posts.EditAt, Posts.DeleteAt""",
            ("%" + term + "%",))
        posts = c.fetchall()

        return render_template('search_by_term.html', posts=posts)

    return render_template('search.html', form=form)


if __name__ == '__main__':
    app.run(host='0.0.0.0')
