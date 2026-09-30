#!/bin/bash

wget https://datasets.imdbws.com/title.basics.tsv.gz -O- | gzip -dv > tsv/title.basics.tsv
wget https://datasets.imdbws.com/name.basics.tsv.gz -O- | gzip -dv > tsv/name.basics.tsv
wget https://datasets.imdbws.com/title.principals.tsv.gz -O- | gzip -dv > tsv/title.principals.tsv
