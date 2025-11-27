### Simple conversion functions such as going from an oxide mass to a uranium mass ###


def U3O8_to_U(U3O8_mass):
    """
    Convert a U3O8 mass to a uranium mass.

    The mass of one mole of U3O8 is equal to the mass of 3 moles of U and 8 moles of O.
    """
    U_molar_mass = 0.238  # kg/mol
    O_molar_mass = 0.016  # kg/mol
    U3O8_molar_mass = 3 * U_molar_mass + 8 * O_molar_mass

    # mass fraction of uranium in U3O8
    U_mass_fraction = (3 * U_molar_mass) / U3O8_molar_mass
    U_mass = U3O8_mass * U_mass_fraction
    return U_mass


def UO2_to_U(UO2_mass):
    """
    Convert a UO2 mass to a uranium mass.

    The mass of one mole of UO2 is equal to the mass of 1 mole of U and 2 moles of O.
    """
    U_molar_mass = 0.238  # kg/mol
    O_molar_mass = 0.016  # kg/mol
    UO2_molar_mass = U_molar_mass + 2 * O_molar_mass

    U_mass_fraction = U_molar_mass / UO2_molar_mass
    U_mass = UO2_mass * U_mass_fraction
    return U_mass

