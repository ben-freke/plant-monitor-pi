from awscrt import io, mqtt, auth, http
from awsiot import mqtt_connection_builder
from coral.enviro.board import EnviroBoard
from luma.core.render import canvas
import time as t
import json
import signal
import sys
import argparse

config_options = {}
mqtt_connection = None
enviro = None


def disconnect():
    print('\nDisconnecting...')
    disconnect_future = mqtt_connection.disconnect()
    disconnect_future.result()


def signal_handler(sig, frame):
    disconnect()
    sys.exit(0)


def connect():
    event_loop_group = io.EventLoopGroup(1)
    host_resolver = io.DefaultHostResolver(event_loop_group)
    client_bootstrap = io.ClientBootstrap(event_loop_group, host_resolver)
    connection = mqtt_connection_builder.mtls_from_path(
        endpoint=config_options['aws_iot_endpoint'],
        cert_filepath=config_options['certificate_path'],
        pri_key_filepath=config_options['private_key_path'],
        client_bootstrap=client_bootstrap,
        ca_filepath=config_options['root_ca_path'],
        client_id=config_options['client_id'],
        clean_session=False,
        keep_alive_secs=config_options['update_frequency'] * 10
    )
    print("Connecting to {} with client ID '{}'...".format(
        config_options['aws_iot_endpoint'], config_options['client_id']))
    # Make the connect() call
    connect_future = connection.connect()
    # Future.result() waits until a result is available
    connect_future.result()
    print("Connected!")
    return connection


def send_data(message_type, data):
    topic = config_options['parent_topic'] + message_type
    message = {
        "client_id": config_options['client_id'],
        "type": message_type,
        "data": data,
        "timestamp": t.time()
    }
    mqtt_connection.publish(topic=topic, payload=json.dumps(message), qos=mqtt.QoS.AT_LEAST_ONCE)
    print("Published: '" + json.dumps(message) + "' to the topic: " + topic)


def collect_data():
    while True:
        data = {
            'temperature': _none_to_nan(enviro.temperature),
            'humidity': _none_to_nan(enviro.humidity),
            'light': _none_to_nan(enviro.ambient_light),
            'pressure': _none_to_nan(enviro.pressure),
            'moisture': process_moisture(_none_to_nan(enviro.grove_analog))
        }
        print(data)
        for sensor, reading in data.items():
            send_data(sensor, reading)
        process_screen_updates(data, sleep_period=config_options['update_frequency'] // 3)


def process_screen_updates(data, sleep_period):
    msg = 'Temperature: %.2f C \n' % data['temperature']
    msg += 'Humidity: %.2f \n' % data['humidity']
    update_display(msg)
    t.sleep(sleep_period)
    msg = 'Light: %.2f lux \n' % data['light']
    msg += 'Pressure: %.2f kPa \n' % data['pressure']
    update_display(msg)
    t.sleep(sleep_period)
    msg = 'Moisture: %.2f%% \n' % data['moisture']
    msg += 'iot.benfreke.org'
    update_display(msg)
    t.sleep(sleep_period)


def update_display(msg):
    with canvas(enviro.display) as draw:
        draw.text((0, 0), msg, fill='white')


def process_moisture(value):
    if value is float('nan'):
        return value
    else:
        return 100 - (((value - config_options['moisture_min']) / (
                config_options['moisture_max'] - config_options['moisture_min'])) * 100)


def _none_to_nan(val):
    return float('nan') if val is None else val


def read_config(file="sensor_config.txt"):
    global config_options
    config_options = {}
    with open(file) as config_file:
        for line in config_file:
            name, var = line.partition("=")[::2]
            config_options[name.strip()] = str(var.strip())
    required_options = ["aws_iot_endpoint", "client_id", "certificate_path", "private_key_path", "root_ca_path",
                        "parent_topic", "update_frequency", "moisture_max", "moisture_min"]
    if all(k in config_options for k in required_options):
        print("All config options present. Loaded:")
        print(config_options)
        config_options['update_frequency'] = int(config_options['update_frequency'])
        config_options['moisture_max'] = int(config_options['moisture_max'])
        config_options['moisture_min'] = int(config_options['moisture_min'])
        return True
    else:
        print("Options are missing from config.")
        return False

def parse_arguments():
    parser = argparse.ArgumentParser("sensor_config")
    parser.add_argument("config_file", help="Specifies the configuration file used by the script.", type=str)
    args = parser.parse_args()
    return args

def main():
    # Setup signal handler for graceful exit
    signal.signal(signal.SIGINT, signal_handler)
    args = parse_arguments()
    # Import config options from file. If it fails, stop the script.
    if not read_config(args.config_file):
        sys.exit(1)
    # Setup global variables
    global mqtt_connection
    mqtt_connection = connect()
    global enviro
    enviro = EnviroBoard()
    # Start data collection
    collect_data()


if __name__ == '__main__':
    main()
