import sys
import zmq
import struct
import array
import numpy as np

def make_socket(port):
    '''
    Generate a subscriber socket with the same settings as the
    original C++ program.
    '''

    print(f'Acquiring socket {port}... ', end='', flush=True)
    subscriber = ctx.socket(zmq.SUB)
    subscriber.setsockopt(zmq.RCVHWM, 0)
    subscriber.setsockopt(zmq.RCVBUF, 10*20000*1030)
    subscriber.setsockopt_string(zmq.SUBSCRIBE, "")
    subscriber.setsockopt(zmq.RCVTIMEO, 100)
    subscriber.connect(f'tcp://localhost:{port}')

    more = True
    while more:
        try:
            msg = subscriber.recv()
        except zmq.ZMQError as e:
            continue
        more = subscriber.getsockopt(zmq.RCVMORE)
    print('acquired.', flush=True)

    return subscriber

if __name__ == '__main__':
    ctx = zmq.Context.instance()

    filt = make_socket(7205)
    raw = make_socket(7204)

    while True:
        # Sometimes the publisher will be interrupted, so don't let that
        # crash the entire program, just skip the frame.
        frame_number = frame_raw = events_data = filt_data = raw_data = weird_data = None
        try:
            # The first component of each message is the frame number as
            # a long long, so unpack that.
            frame_raw = struct.unpack('Q', raw.recv())[0]
            frame_number = struct.unpack('Q', filt.recv())[0]

            # Grab the frame data from both raw and filtered channels.
            if filt.getsockopt(zmq.RCVMORE):
                filt_data = filt.recv()
            if raw.getsockopt(zmq.RCVMORE):
                raw_data = raw.recv()

            # Only filtered has spike events; ignore these.
            if filt.getsockopt(zmq.RCVMORE):
                events_data = filt.recv()

            # Looking for extra data.
            if raw.getsockopt(zmq.RCVMORE):
                print(frame_number)
                while raw.getsockopt(zmq.RCVMORE):
                    weird_data = raw.recv()
                    print(f'There was more data, size {len(weird_data)}.')

        except Exception as e:
            print(e)
            continue

        # `frame_data` is a 1027-element array containing the recorded voltage
        # at each electrode, so unpack that into a usable format.
        filt_arr = np.array(array.array('f', filt_data))
        raw_arr = np.array(array.array('f', raw_data))

        # Don't bother reading the events in this one, just check the size adn
        # frame number of the two floating-point data frames.
        print(f'Frame #{frame_number} (raw #{frame_raw}, Δ={frame_raw-frame_number}):')
        print(f'  raw has {len(raw_arr)} points, from {raw_arr.min()} to {raw_arr.max()}')
        print(f' filt has {len(filt_arr)} points, from {filt_arr.min()} to {filt_arr.max()}')

    # If you split this code into multiple threads, e.g. to consolidate
    # this script with the one that handles the recordings, it will be
    # necessary to delete each subscriber to the ZMQ context separately
    # using the usual Python operator `del`, and then terminate the
    # context with `ctx.term()`. In a single-threaded script like this,
    # though, it's fine to just let the Python interpreter run all these
    # destructors when the program terminates.
