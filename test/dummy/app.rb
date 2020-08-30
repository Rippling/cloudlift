require 'sinatra'
require 'redis'
require 'time'

get '/' do
  redis_client = Redis.new(host: ENV['REDIS_HOST'])
  "This is dummy app. Label: #{ENV['LABEL']}. Redis PING: #{redis_client.ping}"
end

get '/list-mount-files' do
    ls_content = `ls #{ENV['MOUNT_PATH']}`.gsub("\n", "<br/>")
    "<h4>File list @ #{ENV['MOUNT_PATH']}</h4> #{ls_content}"
end

get '/make-mount-file' do
    filename = File.join(ENV['MOUNT_PATH'].to_s, "#{`hostname`.strip}_#{Time.now.utc.iso8601}")
    if system("touch #{filename}")
        "Created #{filename}"
    else
        "Failed creating file #{filename}"
    end
end

get '/elb-check' do
  "This is dummy app. Label: #{ENV['LABEL']}"
end