FROM ruby:2.4.4

RUN apt-get update && apt-get install awscli jq -y

ENV APP_HOME /app/
RUN mkdir -p ${APP_HOME}
WORKDIR $APP_HOME

RUN gem install bundler

COPY Gemfile* $APP_HOME
RUN bundle install

ADD . ${APP_HOME}

ENTRYPOINT ["./docker-entrypoint.sh"]

CMD [ "./run-server.sh" ]