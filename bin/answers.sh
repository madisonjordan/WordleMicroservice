#!/bin/bash

# load json file using python
PARSE=`python3 - <<'EOF'
import json;
file = open('./share/answers.json');
answers = json.load(file);
file.close();
for word in answers:
    print(word);
EOF`

# populate database
DB='answers.db'

# create table from answers
# add column to answers.db for dates starting from tomorrow to end of database
# use "day" column as primary key
if [ ! -f "./var/$DB" ]
then
    mkdir -p var/log
    echo -e ${PARSE} | sqlite-utils insert ./var/$DB answers - \
    --text --convert '({"word": w} for w in text.split())' \
    && cat ./bin/date_gen.py | sqlite-utils convert ./var/$DB answers rowid - --output day \
    && sqlite-utils transform ./var/$DB answers --pk day
else
    echo "$DB already exists"
fi


#############################################
#  CREATE TABLE "answers" (                 #
#    [word] TEXT,                           #
#    [day] TEXT PRIMARY KEY                 #
# );                                        #
#############################################