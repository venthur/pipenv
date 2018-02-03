# -*- coding=utf-8 -*-
import logging
from pip.exceptions import InstallationError
from pip.req import req_set
from pip.wheel import Wheel


logger = logging.getLogger(__name__)


class RequirementSet(req_set.RequirementSet):
    def __init__(self, *args, **kwargs):
        self.valid_tags = kwargs.pop('valid_tags')
        super(RequirementSet, self).__init__(*args, **kwargs)

    def add_requirement(self, install_req, parent_req_name=None,
                        extras_requested=None, supported_tags=None):
        """Add install_req as a requirement to install.

        :param parent_req_name: The name of the requirement that needed this
            added. The name is used because when multiple unnamed requirements
            resolve to the same name, we could otherwise end up with dependency
            links that point outside the Requirements set. parent_req must
            already be added. Note that None implies that this is a user
            supplied requirement, vs an inferred one.
        :param extras_requested: an iterable of extras used to evaluate the
            environement markers.
        :return: Additional requirements to scan. That is either [] if
            the requirement is not applicable, or [install_req] if the
            requirement is applicable and has just been added.
        """
        name = install_req.name
        if not install_req.match_markers(extras_requested):
            logger.warning("Ignoring %s: markers '%s' don't match your "
                           "environment", install_req.name,
                           install_req.markers)
            return []

        # This check has to come after we filter requirements with the
        # environment markers.
        if install_req.link and install_req.link.is_wheel:
            wheel = Wheel(install_req.link.filename)
            if not wheel.supported(self.valid_tags):
                raise InstallationError(
                    "%s is not a supported wheel on this platform." %
                    wheel.filename
                )

        install_req.as_egg = self.as_egg
        install_req.use_user_site = self.use_user_site
        install_req.target_dir = self.target_dir
        install_req.pycompile = self.pycompile
        install_req.is_direct = (parent_req_name is None)

        if not name:
            # url or path requirement w/o an egg fragment
            self.unnamed_requirements.append(install_req)
            return [install_req]
        else:
            try:
                existing_req = self.get_requirement(name)
            except KeyError:
                existing_req = None
            if (parent_req_name is None and existing_req and not
                    existing_req.constraint and
                    existing_req.extras == install_req.extras and not
                    existing_req.req.specifier == install_req.req.specifier):
                raise InstallationError(
                    'Double requirement given: %s (already in %s, name=%r)'
                    % (install_req, existing_req, name))
            if not existing_req:
                # Add requirement
                self.requirements[name] = install_req
                # FIXME: what about other normalizations?  E.g., _ vs. -?
                if name.lower() != name:
                    self.requirement_aliases[name.lower()] = name
                result = [install_req]
            else:
                # Assume there's no need to scan, and that we've already
                # encountered this for scanning.
                result = []
                if not install_req.constraint and existing_req.constraint:
                    if (install_req.link and not (existing_req.link and
                       install_req.link.path == existing_req.link.path)):
                        self.reqs_to_cleanup.append(install_req)
                        raise InstallationError(
                            "Could not satisfy constraints for '%s': "
                            "installation from path or url cannot be "
                            "constrained to a version" % name)
                    # If we're now installing a constraint, mark the existing
                    # object for real installation.
                    existing_req.constraint = False
                    existing_req.extras = tuple(
                        sorted(set(existing_req.extras).union(
                               set(install_req.extras))))
                    logger.debug("Setting %s extras to: %s",
                                 existing_req, existing_req.extras)
                    # And now we need to scan this.
                    result = [existing_req]
                # Canonicalise to the already-added object for the backref
                # check below.
                install_req = existing_req
            if parent_req_name:
                parent_req = self.get_requirement(parent_req_name)
                self._dependencies[parent_req].append(install_req)
            return result
