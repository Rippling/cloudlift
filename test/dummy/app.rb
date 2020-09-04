require 'sinatra'
require 'redis'

get '/' do
  begin
    redis_client = Redis.new(host: ENV['REDIS_HOST'])
     "This is dummy app. Label: #{ENV['LABEL']}. Redis PING: #{redis_client.ping}"
  rescue => e
      "This is dummy app. Label: #{ENV['LABEL']}. Redis PING: ERROR WHILE CONNECTING"
  end
end

get '/elb-check' do
  "This is dummy app. Label: #{ENV['LABEL']}"
end