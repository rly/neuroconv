import unittest
import pytest
from datetime import datetime

import numpy as np
import numpy.testing as npt
from pynwb import NWBHDF5IO
from parameterized import parameterized, param
from spikeinterface.core import BaseRecording


from neuroconv import NWBConverter
from neuroconv.datainterfaces import NeuroScopeLFPInterface, AxonaLFPDataInterface

# enable to run locally in interactive mode
try:
    from ..setup_paths import ECEPHY_DATA_PATH as DATA_PATH
    from ..setup_paths import OUTPUT_PATH
except ImportError:
    from setup_paths import ECEPHY_DATA_PATH as DATA_PATH
    from setup_paths import OUTPUT_PATH

if not DATA_PATH.exists():
    pytest.fail(f"No folder found in location: {DATA_PATH}!")


def custom_name_func(testcase_func, param_num, param):
    interface_name = param.kwargs["data_interface"].__name__
    reduced_interface_name = interface_name.replace("Recording", "").replace("Interface", "").replace("Sorting", "")

    return (
        f"{testcase_func.__name__}_{param_num}_"
        f"{parameterized.to_safe_name(reduced_interface_name)}"
        f"_{param.kwargs.get('case_name', '')}"
    )


class TestEcephysLFPNwbConversions(unittest.TestCase):
    savedir = OUTPUT_PATH

    parameterized_lfp_list = [
        param(
            data_interface=AxonaLFPDataInterface,
            interface_kwargs=dict(file_path=str(DATA_PATH / "axona" / "dataset_unit_spikes" / "20140815-180secs.eeg")),
        ),
        param(
            data_interface=NeuroScopeLFPInterface,
            interface_kwargs=dict(
                file_path=str(DATA_PATH / "neuroscope" / "dataset_1" / "YutaMouse42-151117.eeg"),
                xml_file_path=str(DATA_PATH / "neuroscope" / "dataset_1" / "YutaMouse42-151117.xml"),
            ),
        ),
    ]

    @parameterized.expand(input=parameterized_lfp_list, name_func=custom_name_func)
    def test_convert_lfp_to_nwb(self, data_interface, interface_kwargs, case_name=""):
        nwbfile_path = str(self.savedir / f"{data_interface.__name__}_{case_name}.nwb")

        class TestConverter(NWBConverter):
            data_interface_classes = dict(TestLFP=data_interface)

        converter = TestConverter(source_data=dict(TestLFP=interface_kwargs))
        for interface_kwarg in interface_kwargs:
            if interface_kwarg in ["file_path", "folder_path"]:
                self.assertIn(member=interface_kwarg, container=converter.data_interface_objects["TestLFP"].source_data)
        metadata = converter.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())
        converter.run_conversion(nwbfile_path=nwbfile_path, overwrite=True, metadata=metadata)
        recording = converter.data_interface_objects["TestLFP"].recording_extractor
        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile = io.read()
            nwb_lfp_electrical_series = nwbfile.processing["ecephys"]["LFP"]["ElectricalSeriesLFP"]
            nwb_lfp_unscaled = nwb_lfp_electrical_series.data[:]
            nwb_lfp_conversion = nwb_lfp_electrical_series.conversion
            if not isinstance(recording, BaseRecording):
                raise ValueError("recordings of interfaces should be BaseRecording objects from spikeinterface ")

            npt.assert_array_equal(x=recording.get_traces(return_scaled=False), y=nwb_lfp_unscaled)
            # This can only be tested if both gain and offest are present
            if recording.has_scaled_traces():
                channel_conversion = nwb_lfp_electrical_series.channel_conversion
                nwb_lfp_conversion_vector = (
                    channel_conversion[:]
                    if channel_conversion is not None
                    else np.ones(shape=nwb_lfp_unscaled.shape[1])
                )

                nwb_lfp_offset = nwb_lfp_electrical_series.offset
                recording_data_volts = recording.get_traces(return_scaled=True) * 1e-6
                nwb_data_volts = nwb_lfp_unscaled * nwb_lfp_conversion_vector * nwb_lfp_conversion + nwb_lfp_offset
                npt.assert_array_almost_equal(x=recording_data_volts, y=nwb_data_volts)


if __name__ == "__main__":
    unittest.main()
