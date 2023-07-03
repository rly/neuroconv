import uuid
import warnings
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional

from pynwb import NWBFile

from .tools.nwb_helpers import make_nwbfile_from_metadata, make_or_load_nwbfile
from .utils import get_schema_from_method_signature, load_dict_from_file, dict_deep_update
from .utils.dict import DeepDict


class BaseDataInterface(ABC):
    """Abstract class defining the structure of all DataInterfaces."""

    keywords: List[str] = []

    @classmethod
    def get_source_schema(cls):
        """Infer the JSON schema for the source_data from the method signature (annotation typing)."""
        return get_schema_from_method_signature(cls, exclude=["source_data"])

    def __init__(self, verbose: bool = False, **source_data):
        self.verbose = verbose
        self.source_data = source_data

    def get_conversion_options_schema(self):
        """Infer the JSON schema for the conversion options from the method signature (annotation typing)."""
        return get_schema_from_method_signature(self.add_to_nwbfile, exclude=["nwbfile", "metadata"])

    def get_metadata_schema(self):
        """Retrieve JSON schema for metadata."""
        metadata_schema = load_dict_from_file(Path(__file__).parent / "schemas" / "base_metadata_schema.json")
        return metadata_schema

    def get_metadata(self):
        """Child DataInterface classes should override this to match their metadata."""
        metadata = DeepDict()
        metadata["NWBFile"]["session_description"] = "Auto-generated by neuroconv"
        metadata["NWBFile"]["identifier"] = str(uuid.uuid4())

        return metadata

    def create_nwbfile(self, metadata=None, **conversion_options):
        nwbfile = make_nwbfile_from_metadata(metadata)
        self.add_to_nwbfile(nwbfile, metadata=metadata, **conversion_options)
        return nwbfile

    @abstractmethod
    def add_to_nwbfile(self, nwbfile: NWBFile, **conversion_options):
        raise NotImplementedError()

    def run_conversion(
        self,
        nwbfile_path: Optional[str] = None,
        nwbfile: Optional[NWBFile] = None,
        metadata: Optional[dict] = None,
        overwrite: bool = False,
        **conversion_options,
    ):
        """
        Run the NWB conversion for the instantiated data interface.

        Parameters
        ----------
        nwbfile_path : FilePathType
            Path for where to write or load (if overwrite=False) the NWBFile.
            If specified, the context will always write to this location.
        nwbfile : NWBFile, optional
            An in-memory NWBFile object to write to the location.
        metadata : dict, optional
            Metadata dictionary with information used to create the NWBFile when one does not exist or overwrite=True.
        overwrite : bool, default: False
            Whether to overwrite the NWBFile if one exists at the nwbfile_path.
            The default is False (append mode).
        """
        if nwbfile_path is None:
            warnings.warn(
                "Using DataInterface.run_conversion() without specifying nwbfile_path is deprecated. To create an "
                "NWBFile object in memory, use DataInterface.create_nwbfile(). To append to an existing NWBFile object,"
                " use DataInterface.add_to_nwbfile()."
            )
        
        base_metadata = self.get_metadata()
        if metadata is None:
            metadata = {}
        metadata = dict_deep_update(base_metadata, metadata)

        with make_or_load_nwbfile(
            nwbfile_path=nwbfile_path,
            nwbfile=nwbfile,
            metadata=metadata,
            overwrite=overwrite,
            verbose=getattr(self, "verbose", False),
        ) as nwbfile_out:
            self.add_to_nwbfile(nwbfile_out, metadata=metadata, **conversion_options)
