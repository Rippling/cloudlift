from troposphere import AWSProperty
from troposphere.ecs import DockerVolumeConfiguration, Host, Volume


class EFSVolumeConfiguration(AWSProperty):
    props = {
        'FilesystemId': (str, True),
        'RootDirectory': (str, False),
        'TransitEncryption': (str, False),
    }


class EfsCapableVolume(Volume):
    props = {
        'DockerVolumeConfiguration': (DockerVolumeConfiguration, False),
        'Name': (str, True),
        'Host': (Host, False),
        'EFSVolumeConfiguration': (EFSVolumeConfiguration, False)
    }
