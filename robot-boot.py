from robot import Robot


if __name__ == '__main__':
    with Robot() as robot:
        try:
            robot.start_listening()
        except KeyboardInterrupt:
            pass
