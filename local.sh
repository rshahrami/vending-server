#!/bin/bash
# this is deploy local


ENV_NAME=.back-end-env
ENV_FILE=$PWD/$ENV_NAME
BACK_END_NAME=back
SETTING_FILE=$PWD/back-end/back/A/settings.py


echo "Enter port number(default=8000): "
read port

function deploy() {
    source $ENV_NAME/bin/activate
    pip install --upgrade pip
    cd back-end
    pip install -r requirements.txt
    python back/manage.py runserver 0.0.0.0:$port
}


if [[ -n "$port" ]];
then
    echo "the port number is $port"
else
    port=8000
    echo "the port number is $port"
fi


if [ -f $ENV_FILE ];
then
    deploy
else

    python3 -m venv $ENV_NAME
    deploy
fi
