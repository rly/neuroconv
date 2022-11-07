import os
import shutil
import unittest
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from tempfile import mkdtemp

import numpy as np
from dateutil.tz import gettz
from hdmf.testing import TestCase
from numpy.testing import assert_array_equal
from pynwb import NWBHDF5IO
from scipy.io.wavfile import read

from neuroconv import NWBConverter
from neuroconv.datainterfaces.behavior.audio.audiointerface import (
    AudioInterface,
)

try:
    import soundfile as sf

    skip_test = False
except ImportError:
    skip_test = True


@unittest.skipIf(skip_test, "soundfile not installed")
class TestAudioInterface(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.session_start_time = datetime.now(tz=gettz(name="US/Pacific"))
        cls.num_frames = 10000
        cls.num_audio_files = 3
        cls.sampling_rate = 500

    def setUp(self):
        self.test_dir = Path(mkdtemp())

        self.create_audio_files()
        self.file_paths = [self.test_dir / file for file in os.listdir(self.test_dir) if file.endswith(".wav")]

        self.nwbfile_path = str(self.test_dir / "audio_test.nwb")
        self.nwb_converter = self.create_audio_converter()
        self.metadata = self.nwb_converter.get_metadata()
        self.metadata["NWBFile"].update(session_start_time=self.session_start_time)
        self.starting_times = [0.0, 20.0, 40.0]

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def create_audio_files(self):
        for audio_file_ind in range(self.num_audio_files):
            sf.write(
                file=self.test_dir / f"test_audio_file_{audio_file_ind}.wav",
                data=np.random.randn(self.num_frames, 2),
                samplerate=self.sampling_rate,
            )

    def create_audio_converter(self):
        class AudioTestNWBConverter(NWBConverter):
            data_interface_classes = dict(Audio=AudioInterface)

        source_data = dict(Audio=dict(file_paths=self.file_paths))
        return AudioTestNWBConverter(source_data)

    def test_unsupported_format(self):
        exc_msg = "The currently supported file format for audio is WAV file. Some of the provided files does not match this format: ['.test']."
        with self.assertRaisesWith(ValueError, exc_msg=exc_msg):
            AudioInterface(file_paths=["test.test"])

    def test_get_metadata(self):
        audio_interface = AudioInterface(file_paths=self.file_paths)
        metadata = audio_interface.get_metadata()
        audio_metadata = metadata["Behavior"]["Audio"]

        self.assertEqual(len(audio_metadata), self.num_audio_files)

    def test_incorrect_write_as(self):
        expected_error_message = "Audio can be written either as 'stimulus' or 'acquisition'."
        with self.assertRaisesWith(exc_type=AssertionError, exc_msg=expected_error_message):
            conversion_opts = dict(Audio=dict(write_as="test"))
            self.nwb_converter.run_conversion(
                nwbfile_path=self.nwbfile_path,
                metadata=self.metadata,
                conversion_options=conversion_opts,
            )

    def test_write_as_acquisition(self):
        conversion_opts = dict(Audio=dict(write_as="acquisition", starting_times=self.starting_times))
        self.nwb_converter.run_conversion(
            nwbfile_path=self.nwbfile_path,
            metadata=self.metadata,
            conversion_options=conversion_opts,
        )
        with NWBHDF5IO(path=self.nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            container = nwbfile.acquisition
            metadata = self.nwb_converter.get_metadata()
            for audio_ind, audio_metadata in enumerate(metadata["Behavior"]["Audio"]):
                audio_interface_name = audio_metadata["name"]
                assert audio_interface_name in container
                assert audio_interface_name not in nwbfile.stimulus

    def test_incomplete_metadata(self):
        metadata = deepcopy(self.metadata)
        metadata["Behavior"].update(Audio=[dict(name="Audio", description="Acoustic waveform series.")])
        expected_error_message = (
            "Incomplete metadata (number of metadata in audio 1)is not equal to the number of file_paths 3"
        )
        with self.assertRaisesWith(exc_type=AssertionError, exc_msg=expected_error_message):
            self.nwb_converter.run_conversion(
                nwbfile_path=self.nwbfile_path,
                metadata=metadata,
            )

    def test_not_all_metadata_are_unique(self):
        self.metadata["Behavior"].update(
            Audio=[
                dict(name="Audio", description="Acoustic waveform series."),
                dict(name="Audio", description="Acoustic waveform series."),
                dict(name="Audio2", description="Acoustic waveform series."),
            ],
        )
        expected_error_message = "Some of the names for AcousticWaveformSeries are not unique."
        with self.assertRaisesWith(exc_type=AssertionError, exc_msg=expected_error_message):
            self.nwb_converter.run_conversion(
                nwbfile_path=self.nwbfile_path,
                metadata=self.metadata,
            )

    def test_starting_times_are_floats(self):
        conversion_opts = dict(Audio=dict(starting_times=[0, 1, 2]))
        expected_error_message = "Argument 'starting_times' must be a list of floats."
        with self.assertRaisesWith(exc_type=AssertionError, exc_msg=expected_error_message):
            self.nwb_converter.run_conversion(
                nwbfile_path=self.nwbfile_path,
                metadata=self.metadata,
                conversion_options=conversion_opts,
            )

    def test_starting_times_does_not_match_metadata(self):
        conversion_opts = dict(Audio=dict(starting_times=[0.0, 1.0, 2.0, 3.0]))
        with self.assertRaises(expected_exception=AssertionError):
            self.nwb_converter.run_conversion(
                nwbfile_path=self.nwbfile_path,
                metadata=self.metadata,
                conversion_options=conversion_opts,
            )

    def test_default_starting_times(self):
        audio_interface = AudioInterface(file_paths=[self.file_paths[0]])
        metadata = audio_interface.get_metadata()
        metadata["NWBFile"].update(session_start_time=self.session_start_time)
        with self.assertWarnsWith(warn_type=UserWarning, exc_msg="starting_times not provided, setting to 0.0"):
            audio_interface.run_conversion(
                nwbfile_path=self.nwbfile_path,
                metadata=metadata,
            )

    def test_run_conversion(self):
        conversion_opts = dict(Audio=dict(starting_times=self.starting_times))
        self.nwb_converter.run_conversion(
            nwbfile_path=self.nwbfile_path,
            metadata=self.metadata,
            conversion_options=conversion_opts,
        )
        file_paths = self.nwb_converter.data_interface_objects["Audio"].source_data["file_paths"]
        audio_test_data = [read(filename=file_path, mmap=True)[1] for file_path in file_paths]

        with NWBHDF5IO(path=self.nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            container = nwbfile.stimulus
            metadata = self.nwb_converter.get_metadata()
            self.assertEqual(3, len(container))
            for audio_ind, audio_metadata in enumerate(metadata["Behavior"]["Audio"]):
                audio_interface_name = audio_metadata["name"]
                assert audio_interface_name in container
                self.assertEqual(
                    self.starting_times[audio_ind],
                    container[audio_interface_name].starting_time,
                )
                self.assertEqual(
                    self.sampling_rate,
                    container[audio_interface_name].rate,
                )
                assert_array_equal(
                    audio_test_data[audio_ind],
                    container[audio_interface_name].data,
                )
